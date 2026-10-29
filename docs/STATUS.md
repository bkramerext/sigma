## Issue #306 and happy-path reliability (#302) (2026-10-28)

Research limits now say **Research rounds** and **Maximum agent turns**. A round
is an Investigator/Skeptic exchange for one strategy; the shared turn budget
can be smaller than twice the round ceiling or the number of selected
strategies. The scheduler rotates across strategies, reserves complete pairs,
and records any deferred strategy explicitly. Defaults are 2 rounds, 12 turns,
30 minutes, 4,000 output tokens per call, one concurrent session, and no
optional input-token or cost cap. These settings limit routine provider use
without forcing users into higher token or duration ceilings.

The frontend and backend accept the same ranges and require at least one full
two-turn pair. USD cost entry accepts surrounding whitespace and an optional
leading `$`, then persists a normalized numeric USD value. A proposed
productive stop is reopened when reviewed evidence leaves objective obligations
unresolved and the saved limits allow another round. Provider response bodies
and completed SSE streams are bounded at 8 MB; the prior 1 MB transport bound
rejected large successful Responses envelopes (including session #11's
reported >1 MB response). The Maximum Regions browser acceptance measured a
3,801-byte project payload and 5,410-byte assembled provider context, so this
sample's 1 MB issue is not project-data overhead. The larger stream bound is
still bounded and regression-tested at both 1 MB and 8 MB.

Deterministic browser acceptance with SIGMA, Chrome, and the local provider
fixture passed: sample copy, USD round-trip, Investigator/Skeptic order, usage
and estimated cost accounting, mathematical candidate, terminal status,
report export, refresh and reopening. It measured two simulated provider calls
and $0.004008 estimated usage. This was fixture traffic, not a live provider
session. Focused project-settings, research-session, Sage execution, Ruff,
Pyright, frontend typecheck, production build, and full `./sigma test` all
passed. Live provider behavior is **UNVERIFIED**; no paid call was authorized
or made. See `messages/issue_306_happy_path_r4r.md` for the full Software
Factory handoff.

## Backend access log build SHA (2026-10-28)

Uvicorn access entries place the seven-character SHA immediately after the
client IP address and port. The backend
uses the configured build commit when supplied, or the checkout HEAD for a
local launch. A local restart is needed to see the new format.

## Context-aware AI text conversion (2026-10-28)

The shared AI Plain/Markdown conversion prompt now asks the model to decide
slash notation from sentence context: `good/better` in prose remains wording,
while `1/2 the people in this room` expresses a fraction. It explicitly keeps
ordinary slash-separated words out of math delimiters and LaTeX fractions.
The conversion still preserves the source and uses the existing structured
response path. Offline request assertions cover both API-key and ChatGPT-plan
payloads; live model quality remains unverified. `tests/text_views.py` passed
after the prompt change. The full `./sigma test` ran through the Python and
frontend suites but failed at an outdated hosted-personal fixture expectation,
two Ruff import-order findings, and three Ruff formatting findings. The
fixture now explicitly selects personal mode before testing it, and those
Ruff findings have been corrected. A second full run passed the hosted-personal
scenario and all Python scenarios, Ruff check, Pyright, and frontend typecheck;
it found one remaining formatting issue in `src/sigma/research_budget.py`, now
corrected. Final verification remains pending.

## Issue #286 — Maximum concurrent sessions (2026-10-27)

Added **Maximum concurrent sessions** to Project Settings → Limits. The
application default is 1. Users can enter any positive decimal integer without
an application-defined maximum; the API carries the value as decimal text so
JavaScript number precision does not truncate it. Legacy projects inherit 1,
and the saved setting remains in the project limits bundle and each new
session's admission snapshot.

Admission and resume count queued/running sessions for that project while
holding the existing cross-process project manager lock. The hosted reservation
ledger also checks the per-project count inside its SQLite write transaction.
For pre-upgrade rows, it verifies a matching saved session record and project ID
before counting a legacy row or assigning its slot marker. Legacy rows with an
empty project path are resolved against the current project's record; standalone
inference rows without a research-session record remain outside this limit.
Other projects are no longer blocked by a local active-session check. Raising
the value admits new sessions immediately; lowering it leaves current sessions
alone and blocks additional admission while the count is at or above the new
limit. Completed, failed, stopped, and paused sessions do not consume slots.
Local stale work is recovered before counting. A hosted queued session without
a durable queue reservation is paused with a no-dispatch explanation; running
provider calls retain the existing unknown-completion safeguards and are never
automatically replayed.

Verification: `tests/research_sessions.py` passed concurrent start admission
and capacity reuse after stop; `tests/project_settings.py` passed default,
invalid input, sibling-project isolation, numeric API input, and 100 digit
decimal save/load; `tests/project_bundle.py` passed JSON bundle round-trip with
an 80 digit setting; `tests/cloud_research.py`, `tests/cloud_auth.py`, and
`tests/sage_execution.py` passed hosted admission, interrupted recovery, and
the updated per-project scope. Real Chrome
`browser_checks/issue286_concurrent_sessions.py` passed default-1, zero
rejection, 80 digit save/reopen, and narrow viewport checks using an isolated
local fixture. The full `./sigma test` passed every step, including Ruff,
formatting, Pyright, frontend typecheck, and production build. Vite emitted the
existing advisory for the 519 kB main JavaScript chunk. No paid or live
provider calls, OAuth, or production changes occurred.

PR #287 review follow-up: `tests/cloud_research.py` now models an active
pre-migration session row with `session_slot=0` and an empty legacy project path,
then verifies it blocks a second session after upgrade. The complete
`./sigma test` passed again after this correction.

PR #287 integration with Green's merged sponsored-access and invitation work:
the SQLite per-project admission check and legacy migration remain intact beside
the allowance-window functions, and hosted queued-session recovery checks the
durable sponsor ledger. The single-worker guard was removed from local session
admission so the configured limit applies per project. `./sigma test` passed on
the combined tree. Real Chrome passed
`browser_checks/issue286_concurrent_sessions.py`,
`browser_checks/hosted_sponsored_connection.py`, `browser_checks/guest_samples.py`,
and `browser_checks/issue279_invite_me.py` using local fixtures; no provider
inference or production changes occurred. The #279 browser check now dismisses
the new first-visit welcome and verifies the current identity-pill stack.

The browser-exercised sample copy was exported with SIGMA's complete project
export service; exact bytes and source/session manifest are in
[`docs/evaluations/issue_286/exports`](evaluations/issue_286/exports/README.md).
Implementation branch: `blue/issue-286-concurrent-sessions`; [PR #287](https://github.com/bkramerext/sigma/pull/287)
is open for independent review. See the
[`messages/issue_286_blue_r4r.md`](../messages/issue_286_blue_r4r.md) handoff.

## Sponsored welcome shows current remaining balance (2026-10-27)

Regular local members now start a fresh ChatGPT account authorization from the
Connect to ChatGPT pill instead of reusing the globally active ChatGPT
registration, which may be the designated SIGMA sponsor. This avoids sending
the sponsor registration through the personal connection route. ChatGPT API
errors now display FastAPI's `detail` field rather than the generic “AI account
change failed.” Real Chrome verifies a non-sponsored member with the sponsor
registration active can connect a personal account without submitting the
sponsor account ID; the sponsored selection/reconnect paths remain covered.
The pending-sign-in status no longer puts a Cancel button under the pill;
closing the ChatGPT sign-in popup cancels that pending attempt.

The sponsored welcome dialog now uses the budget's `remaining_usd`, matching the
Sponsored ChatGPT pill, instead of showing the account's original grant. For a
small sponsored balance it says how much remains. Real-Chrome
`browser_checks/hosted_sponsored_connection.py` verifies a $0.25 grant with
$0.21 estimated usage displays $0.04 remaining. The browser acceptance and
`./sigma test` passed. No provider calls or production configuration changes
occurred.

Signing out now marks the guest welcome as already seen for the current tab, so
leaving an authenticated session does not trigger a first-visit greeting. Real
Chrome guest acceptance clears the prior guest-dismissal marker before sign-out
and verifies the dialog remains absent afterward.

## Guest Play continuation and project sign-out (2026-10-27)

Google sign-in from the guest Play prompt now carries the project into the
authorized account's private workspace with the project ID, research history,
evidence, and artifacts preserved. Returning to that project resumes Play into
the ordinary “Start new session #n” confirmation; it does not launch research
automatically. Project-page sign-out makes a separate temporary guest copy and
returns to that project instead of Home. Copies refuse to cross account access
while a session is queued, running, or paused. Real-Chrome guest acceptance
verifies the resumed confirmation, welcome suppression, sign-out staying on the
project, invitation layout, and consistent Google action labels. Focused cloud
auth/workspace and bundle tests passed; `./sigma test` passed for the final
tree, including Pyright, frontend typecheck and production build. No live provider calls, production configuration changes, or deployment
occurred.

Follow-up hardening makes the resume request an allow-listed `resume_play=1`
parameter on SIGMA's validated OAuth return path and carries it through the
guest-to-member workspace copy. The frontend waits until the signed-in project
can start a session, then opens its standard confirmation without auto-running.
The auth gate no longer rewrites signed-out project URLs to Home, so project
sign-out stays on the copied guest project. One-time invitation welcomes
depend on the persisted pending flag. Sponsored non-admin accounts also see
their sponsored welcome on a fresh app entry, but not on reload; administrators
are excluded. Real-Chrome checks cover a non-sponsored member's Play return,
project sign-out, sponsored welcome on fresh entry but not reload, and no admin
welcome. `./sigma test` and both focused real-Chrome checks passed.

## Guest Play sign-in and invitation pill alignment (2026-10-27)

The Home and Project invitation actions now sit directly below and align with
their Google sign-in pills. Invitation-dialog Google sign-in now uses the underlined
SIGMA action-link style and concise “Sign in with Google” label. The signed-out
Play flow stores a tab-scoped intent before starting Google sign-in; when an
eligible user returns to the project,
that intent suppresses the otherwise automatic welcome dialog. Normal sign-in
to Home retains the welcome behavior. Real-Chrome `browser_checks/guest_samples.py`
passed with geometric alignment assertions, consistent “Sign in with Google”
actions in invitation and Ready to Investigate dialogs, and sign-in intent persistence;
`./sigma test` passed, including Ruff, Pyright, frontend typecheck and production
build. No live provider calls, production configuration changes, or deployment
occurred.

## T277 hosted TeX generation HTTP 400 (2026-10-27)

Read-only IAP inspection found production `sigma.service` active and release pin
`0ab399f024f939fa08a1ded215878669639a25e2`. The VM Git HEAD was not read because
Git rejected the SSH principal's ownership context; no safe-directory setting
was changed. Filtered systemd and backend container logs retained no provider
error code/parameter for the reported HTTP 400, so its cause remains
**UNVERIFIED** (request schema, model access, and billing are not distinguished).

T277's isolated branch adds safe API error classification: only allowlisted
provider codes and parameter names can appear in diagnostics; raw messages,
arbitrary values, and research content remain suppressed. Known schema/request,
model-access, and quota/billing classes receive distinct wording, while unknown
400s are explicitly unclassified. Neither the request, selected model/provider,
automatic provider retry behavior, nor spending safeguards changed. `tests/papers.py` covers both
one-shot and long-form request payloads with mocked HTTP 400, asserting strict
Pydantic JSON Schema, selected model/reasoning, `store: false`, bounded output,
and one call per path with no retry. Focused paper and model-connection tests
passed. The full `./sigma test` passed for the final code/test head, including
Ruff, Pyright, frontend typecheck, and production build. Two real-Chrome A20
attempts did not reach paper generation because the isolated mock API returns
404 for `/api/samples`, leaving the expected sample-open control absent;
browser acceptance is UNVERIFIED. No
live provider calls, paid inference, credential inspection,
production configuration changes, or redeployment occurred. See
`messages/t277_red_paper_api_400.txt`.

Follow-up fault-tolerance improvement: one-shot papers now persist an
evidence-validated structured draft in the existing project-private checkpoint
store before TeX compilation. The checkpoint is bound to project ID, frozen
snapshot hash, provider identity/mode, selected model, reasoning effort, and
authoring mode. After compiler failure, an explicit Generate retry recompiles
from that draft with zero additional provider calls; successful publication
removes the checkpoint. Explicit restart archives prior attempt counts. A new
regression injects a compiler failure and verifies one mock inference total,
successful PDF publication on retry, and zero remaining calls in preflight.
Focused paper tests and frontend typecheck pass; the full `./sigma test` passes.

## Hosted sponsored API restoration and release repair (2026-10-27)

Production is configured for SIGMA-sponsored OpenAI API inference with
`SIGMA_CLOUD_INFERENCE_PROVIDER=api_key` and
`SIGMA_CLOUD_SPONSORED_ENABLED=true`. The server-held credential remains in the
Secret Manager-mounted file; no credential was read or exposed. Secret version 1
is enabled and VM runtime access is scoped to that individual secret. Non-billable
credential validation and model discovery passed (`gpt-6-luna`, `gpt-6-astra`,
`gpt-6.1-sol`). Spending and concurrency ceilings were inspected and left intact:
$2 per user, $15 global, concurrency 1 per user/global, queues 2 per user/8
global. No paid production inference was run.

During restoration, the previously installed host preflight script did not
recognize the existing `SIGMA_CLOUD_SPONSORED_ENABLED` setting. It blocked the
systemd pre-start gate before Compose could start. The prior protected config was
restored, the same release was restarted, and the helper was synchronized with
the checked-out release. All 23 production preflight checks passed; backend,
frontend, and edge then returned healthy. `/srv/sigma-state` stayed mounted and
untouched. PR #270 updates `deploy/deploy-gce-release.py` to install the
release-matched preflight helper for candidate and rollback transitions; fixture
rehearsals cover candidate-build failure and source-SHA identity.

PR #270 was deployed as `51fd98735bb16375f4b035a66b76884904336aa9`; PR #271
then fixed history-bearing sample copies and was deployed as
`84edc9f4aa574d17749d61d0a110e56c192c0e04`. The public URL now references
`/assets/index-StWhmoPv.js`, which contains the hosted sponsored pill actions and
no longer contains the old cloud OAuth 403 text. The authenticated UI itself is
not visible to the operator's clean browser, but public sample navigation is
visible and works.

The hosted pill previously called `/api/ai/auth/begin`, intentionally blocked in
hosted mode with `AI provider authorization is unavailable in cloud mode.` It now
selects hosted sponsored mode via `/api/ai/mode`, reflects
`/api/cloud-research/connection` status (not personal ChatGPT state), and does
not silently leave an active sponsor mode. The history-bearing sample 400 was
caused by template session IDs being reused across workspaces; PR #271 assigns
fresh session IDs per copy while preserving references and the ledger ownership
guard.

Focused validation passed: `tests/cloud_auth.py` (47 tests),
`tests/cloud_research_sponsored_api.py` (deterministic mocked inference,
accounting/limits/idempotency/isolation), `tests/deployment_automation.py`,
`browser_checks/hosted_sponsored_connection.py` in real Chrome with mocked API,
`npm --prefix frontend run build`, Ruff and Pyright. `./sigma test` was started
but intentionally stopped at the owner's direction to prioritize deployment;
it had reached the long research-session test when interrupted. One earlier run
also surfaced fixture assumptions for the newly synchronized preflight helper;
those fixtures were corrected and both T173 rehearsals passed afterward.

Issue #265 remains open. Live paid Investigator/Skeptic execution and its
durable artifacts remain **UNVERIFIED**. The owner approved one session with at
most two calls, a $0.25 cap, and no retries, but the operator environment has no
authorized Google member browser session to run it. Public API readiness is
healthy and a clean real-Chrome browser opened the history-bearing sample from
two independent guest workspaces without toast or console errors; authenticated
member pill and research acceptance still need verification. The daily backup
timer is inactive. A fresh consistent snapshot reached READY and a separate
clone disk was successfully restored from it, then deleted; no application
schema migration was part of these releases.

## Hosted sample research-session ID collision (2026-10-27)

The first production cutover exposed a second hosted issue: opening the
history-bearing Nonconsecutive Subset Sums sample returned HTTP 400, `Cannot
open sample working project: Research job is unavailable.` Reproduced against
production from a clean guest browser. Cause: saved sample histories reused the
template session IDs in every new copy, while the cloud research ledger is shared
and binds each session ID to one workspace/project. The owner check correctly
rejected reuse across workspaces.

`src/sigma/samples.py` now assigns each sample copy fresh session IDs and
rebinds exact session-ID references throughout saved history and artifacts. A
new hosted-auth regression opens the same history-bearing sample in two isolated
guest workspaces and verifies each copy succeeds with disjoint session IDs.
`tests/cloud_auth.py` passed all 47 tests; targeted Ruff, format, and whitespace
checks passed. PR #271 is deployed in release
`84edc9f4aa574d17749d61d0a110e56c192c0e04`. Real Chrome opened this sample from
two independent fresh production workspaces without a 400, toast, or page error.
No user data or historical research ledger rows were modified. The fix requires
no provider calls; the sample endpoint failure did not involve inference or
sponsorship.

# SIGMA status

## Issue #280 — sponsored allowance and forced-mode launch flag (2026-10-27)

The hosted account/model pill is labeled **Sponsored ChatGPT** and
exposes the authenticated user's sponsored allowance on hover, keyboard focus,
and tap. Its tooltip reports the per-user remaining amount, allowance ceiling,
estimated use, held amount, and connection/check state. Allowance reads remain
on the authenticated, no-store per-user budget endpoint; provider request
completion triggers a refresh without making an inference call. Forced mode is
identified in the accessible pill name and tooltip.

`SIGMA_CLOUD_FORCE_SPONSORED_MODE` is a deployment-wide, default-off setting
documented in [Cloud Deployment](CLOUD_DEPLOYMENT.md). When enabled together
with sponsored access, authenticated eligible accounts receive sponsored mode
at sign-in/reload, and the server rejects personal-mode changes. Ineligible and
unauthenticated identities remain denied. Existing allowance, global spending,
queue, concurrency, and ledger checks are unchanged. Production configuration
was not changed and the flag was not enabled.

Verification on branch `green/issue-280-sponsor-mode`, based on current main
`918aee4`: `tests/cloud_auth.py` passed (48 tests); `tests/gce_host.py` passed
(21 tests); `browser_checks/hosted_sponsored_connection.py` passed in real
Chrome at 1440px and 390px, including hover, keyboard focus, mobile tap,
allowance refresh after a simulated provider request, and forced mode over two
reloads. `./sigma test` passed all steps, including Ruff (281 files), Pyright,
frontend typecheck/build, and deployment checks. A build-size advisory remains
the existing non-failing Vite warning. No live provider calls, paid inference,
or production changes occurred. See the [Issue #280 R4R handoff](../messages/issue280_green_sponsored_allowance_r4r.txt).

### Issue #280 follow-up — one-time invitation welcome (2026-10-27)

On integration commit `5971d35e`, newly invited eligible accounts receive a
centered, one-time “You have been invited!” dialog after sign-in/reload. The
dialog shows the account's effective remaining sponsored allowance when it is
$1.00 or less, uses the appropriate new-account/credited-account wording, and
chooses one of 100 curiosity-themed messages. It supports Escape and a visible
acknowledgment button; dismissal is persisted server-side, so reloads do not
repeat it. The account state migration defaults existing users to no pending
welcome. Account switching does not reuse another user's allowance.

The home **Invite me!** action sits directly below About on the home header.
For account testing, it is temporarily visible to any account while hosted
sign-in is enabled, including signed-in members, so the Google account chooser
can be opened from an existing session. The invitation endpoint still requires
a verified, server-issued denied-login cookie before it records a request.
After a Google challenge started from that action, an uninvited verified
identity submits the invitation request automatically; success closes the
dialog and removes the action. On delivery failure, the request dialog opens
with one error message and a standard **Try again** button. The invitation
dialog has an underlined, transparent Close action after its title, a Google
sign-in pill with the lower gap 2.5 times the upper gap, and a lower-left
**Privacy Notice** link. Closing the privacy page returns to the invitation dialog; the About
dialog's Privacy Notice link likewise returns to About. The notice body now
describes SIGMA's stored identity, access, invitation, feedback, project, and
sponsored-usage data and remains version 1.0. The artwork credit reads
“Crafted by Brian Kramer” / “and [a randomly selected adjective] OpenAI agents.”

Focused validation passed: `tests/cloud_auth.py` (50 tests), Ruff, frontend
typecheck/build, and `browser_checks/hosted_sponsored_connection.py` in real
Chrome with mocked API, including the one-time behavior, message, amount, and
centering, invitation layout, both privacy return paths, and the automatic
invite-intent submission. `./sigma test` passed all steps, including Ruff,
Pyright, frontend typecheck/build, and deployment checks. The full run exposed a tracked
executable-mode issue in `deploy/gce_preflight.py`; its shebang/mode is now
consistent with Ruff and scripts that invoke it directly. No paid provider
calls, live Google OAuth challenge, or production configuration changes
occurred; the supplied personal account's actual Google challenge therefore
remains unverified.
The browser canvas now uses the home artwork itself as its pre-render startup
background, with `#020711` as its matching dark fallback, to prevent a light
default page flash before the app renders.
In Administrator Settings, the Invitation requests table now removes Status
and widens the verified-account column by one third. Its **Add** action grants
the verified email as a member using the configured default allowance;
existing active email rules show **Added**. The Authorized users table
collapses case/trailing-dot variants and displays the most recently updated
rule, preferring normalized spelling when update times tie.
See [invitation welcome R4R handoff](../messages/issue280_green_invited_welcome_r4r.txt).

## Issue #265 — hosted sponsorship disabled (2026-10-27)

The public 0.1.1 Home UI at `3f2426c6fa83866c655cb1b601a7e2df78e5e459`
passed clean and cache-disabled Chrome checks: Google and ChatGPT pills are
visible, no console/network failures, current assets served. Production
account state subsequently exposed the nonworking sponsored ChatGPT choice.
Per owner direction, the hosted Compose stack now defaults sponsorship off;
the backend rejects sponsored selection and provider access and resets saved
sponsored choices to personal. The Connect to ChatGPT pill remains gated by
Google authentication. Hosted personal ChatGPT authorization remains unavailable
by existing design, so AI inference is not claimed. Focused auth, sponsored
API, deployment package and GCE host tests passed; full test and final hosted
account acceptance are reported separately.

## Issue #265 — 0.1.1 production upgrade (2026-10-27)

Read-only GCE diagnosis found production still running the initial
`e1ef8db8ea6c15bcb79ad9c8d06e8e5f6f4527f3` release: checkout, release pin,
backend/frontend tags, image IDs, and OCI revision labels agree. Host Caddy
routes the public site to the Compose edge; the old Home UI is served by the
old frontend container. The expected state disk UUID is mounted and 23/23
preflight checks pass. The only READY recovery snapshot is from October 26;
no backup scheduler is installed. Production lacks the new 0.1.1 SMTP sender
configuration and protected password file, so cutover remains blocked on an
approved secret and fresh recovery point.

Under owner authorization, a consistent snapshot
`sigma-state-issue265-20261027-075405` was created while the application was
stopped; it reached READY and the prior service restarted healthy. A temporary
recovery VM with no public IP or service account mounted its clone read-only
with the approved UUID. The packaged verifier initially failed because it
looked for the workspace databases in `/auth`, although production stores them
in `/auth/workspaces`. With that path corrected, the verifier passed SQLite
integrity and required tables, 2 identity/workspace mappings, 3 project
records, 10 research artifacts, 0 paper pairs, and accounting references with
1 reserved/unknown call. The temporary recovery VM and disk were removed;
the READY snapshot remains. This is a read-only restore check, not a full
recovery cutover or authenticated browser test.

An exact-source build of target `999db4362656fd5a22d6ebaaf733e64c8e87543e`
failed before any service change: the frontend Vite build reads
`pyproject.toml`, but the Dockerfile did not copy it. The focused fix copies
that file into the image build stage. `./sigma test` and the local real-Chrome
mock-auth walkthrough passed. Both corrected release images built on the VM
from PR #266 commit `df3a5626748d4a5960ca5809d376fb5c7272cb76`, with
matching OCI source labels. Production is unchanged; public 0.1.1
acceptance is **UNMET** pending independent review, configuration, backup, and
verified deployment. No paid provider calls were made.

## PR #257 — T88 visual and research-follow-up refinements (2026-10-26)

On `feature/local-mock-auth-walkthrough`, standardized Home and Project Google
and ChatGPT pill geometry: 34px desktop and 28px narrow-screen height, matching
12px/9px inline padding, and a 13px vertical gap. The SIGMA project-logo
tooltip now has no native browser `title`; the custom tooltip stays at the
cursor-relative point where it first appears. The recent-category running
indicator, suggestion progress treatment, and bounded strategy-suggestion
context are covered by focused regressions. No authentication, workspace,
funding, or provider behavior changed.

`./sigma test` passed, including Ruff check/format (280 files), Pyright (0
diagnostics), frontend typecheck, and production build (existing >500 kB chunk
advisory). Real Chrome passed `browser_checks/t257_mock_auth.py` and
`browser_checks/t92_recent_running.py`. Pill-pair and tooltip screenshots are
in `evaluations/t257/screenshots/green-*-pills-*.png` and
`evaluations/t257/screenshots/green-project-logo-tooltip.png`. Final-head CI
was not polled per the user's instruction; no paid calls or provider
credentials were used.
See the [follow-up handoff](../messages/t88_green_pr257_followup.txt) for
exact commands, evidence, and acceptance disposition.

## PR #257 — T88 Stream B visual consistency (2026-10-27)

Real-Chrome visual checks found and corrected mock selector overflow in the
Project header, account-dialog overlap with its pill on short/narrow screens,
and Home pill stacking behind project content at narrow widths. The dialog
now places itself on the side with more room, caps its height to that space,
and remains scrollable. Browser coverage captures Guest, member, administrator,
and denied/uninvited dialogs on Home and Project at desktop and mobile sizes;
the checks assert viewport bounds, no pill overlap or horizontal overflow, and
focus. Frontend typecheck/build and the focused T88 sign-in and mock-auth
real-Chrome suites passed. No auth or provider behavior changed. See the
[T88 Stream B handoff](../messages/t88_green_stream_b_visual.txt) for exact
screenshots, commands, and disposition.

## PR #257 — T88 Stream A Batches 1–2 (2026-10-27)

Continued the existing `feature/local-mock-auth-walkthrough` PR from
`05cabb5c743b884156cb423433f20e6700b69c2f`, based on current `main`
`14612ff553dd684db993e25c4aedaf83155465ff`. Applied Ruff formatting to the
six CI-identified Python files; review of the whitespace-insensitive diff
shows no behavior changes from formatting. Extended the local mock-identity
request regression to cover cross-member artifact URL access as well as
project and session access. Extended the T88 real-Chrome check to assert one
identity pill and save screenshots of Home and Project with the account dialog
open beneath the pill.

Added `browser_checks/t257_mock_auth.py` as a reproducible real-Chrome check of
the actual local mock selector and API. It covers Guest's empty scoped Recent,
Member A/B project separation, Administrator role with the same allowance as a
member, Uninvited denial and invitation request, and simulated sponsor
exhaustion/provider unavailability through the mock research route. The test
uses temporary storage and blank provider credentials. This route advances a
single saved strategy through deterministic queued/Investigator/Skeptic/result
states, optionally storing only a labeled inconclusive fixture artifact. A
sponsored `$0` allowance or simulated unavailable provider yields a failure
without an artifact; the normal research start, AI, cloud-research, and
non-allowlisted project-write routes remain server-denied in mock mode.
Screenshots are
[Home](evaluations/t257/screenshots/home-account-dialog.png) and
[Project](evaluations/t257/screenshots/project-account-dialog.png).

Verification on the candidate tree: `tests/cloud_auth.py` passed 44 tests;
Ruff check/format and `git diff --check` passed. Real Chrome passed
`browser_checks/t23_1_google_signin.py`,
`browser_checks/t257_mock_auth.py`, `browser_checks/model_availability.py`,
`browser_checks/t92_recent_running.py`, `browser_checks/t201_overflow.py`,
`browser_checks/t81_public_legal_pages.py`, `browser_checks/guest_samples.py`,
and `browser_checks/t47_conclusion.py` (Research Outcome). T201 was run with
`TMPDIR=/private/tmp` to avoid macOS `/tmp` symlink mismatch in its fixture.
The complete `./sigma test` passed, including Ruff (274 files formatted),
Pyright (0 diagnostics), frontend typecheck, and production build; the build
retains its existing >500 kB chunk advisory.

No live OAuth, production deployment, GCP change, paid inference, or provider
credential was used. The browser screenshots show the two-line identity/model
pill and the unified pill-anchored dialog, with no welcome dialog or duplicate
identity pill. This is R4R for independent review, not acceptance. The
separately scoped hosted personal-inference authorization remains unavailable;
live Google/OAuth, hosted provider, GCE, and production multi-account behavior
remain unverified. Batch 3 was not started. See the
[T88 Stream A handoff](../messages/t88_green_pr257_stream_a.txt) for criterion
dispositions and exact commands.

## T81 PR #242 reconciliation with current main (2026-10-26)

Reconciled PR #242 with `origin/main` at
`48fe9a1fee87a23c1af1665f1f30723ef39d9e97`, including merged PR #230. Kept
the current-main Guest startup test and combined it with T81 coverage for the
friendly missing-admin `--signin` error and configured `--signin` credential
handling. Resolved the email-test overlap with the current-main typed bytes
assertion. `src/sigma/cloud_auth.py` merged automatically; the formatter
changes remain present with current-main #230 behavior intact.

`./sigma test` passed all scenarios, Ruff check/format, Pyright (0 diagnostics),
frontend typecheck, and frontend build (existing >500 kB chunk advisory). Real
Chrome passed `browser_checks/t81_public_legal_pages.py` for signed-out direct
navigation and refresh of `/privacy` and `/tos`, draft labels, About Privacy,
and no `/tos` app links. GitHub CI results are recorded in the updated PR and
handoff. No deployment occurred.

## T81 PR #242 CI unblock (2026-10-26)

Updated the stale `tests/tooling.py` startup checks to match current `main`:
ordinary launch without `--signin` works with a blank admin-contact setting
as Guest (`SIGMA_LOCAL_AUTO_ADMIN=false`); `--signin` without the contact
returns its friendly error before constructing the launcher or starting
servers; and configured `--signin` continues to exercise server-only OAuth
credentials and local admin setup. Applied Ruff's formatting-only changes to
three expressions in `src/sigma/cloud_auth.py` without changing behavior.
This file also overlaps Blue's PR #246; the overlap is limited to those
formatting changes and is reported in the Gray handoff for coordinator
reconciliation through Brian.

`./sigma test` passed all scenarios, Ruff check/format, Pyright (0 diagnostics),
frontend typecheck, and production build (existing >500 kB chunk advisory).
Real Chrome passed `browser_checks/t81_public_legal_pages.py` for signed-out
direct navigation and refresh of `/privacy` and `/tos`, draft labels, the About
Privacy link, and absence of app `/tos` links. No deployment occurred. See the
[Gray handoff](../messages/t81_gray_public_legal_pages.txt).

## T81 public legal pages follow-up (2026-10-26)

On current `main` `623a9464fed585cf951b02be54e8e4ab683bb559`, the existing
public `/privacy` route remains labeled as a proposed notice awaiting Brian's
approval. The About dialog link is now clearly labeled **Privacy**. Added a
public `/tos` route with concise proposed terms for experimental research
features. It is visibly marked as a draft for Brian's review, and no `/tos`
navigation link is added to the SIGMA app. The draft is recorded in
[TOS_DRAFT_v1.md](TOS_DRAFT_v1.md); it must be reviewed before production
publication.

Local verification: real Chrome passed direct signed-out navigation and
refresh at `/privacy` and `/tos`, both draft labels, the About Privacy link,
and absence of `/tos` app links. Frontend typecheck and
`npm --prefix frontend run build` passed (existing >500 kB chunk advisory).
`./sigma test` ran the application scenarios and frontend typecheck but exited
1 on current-main Ruff findings in `src/sigma/gmail_delivery.py`,
`src/sigma/ui_instance.py`, and `tests/gmail_delivery.py`, formatting findings
in those files, and the existing Pyright error at
`tests/gmail_delivery.py:56`; the build step was skipped by the suite and then
passed when run directly. The new browser check passes targeted Ruff check and
format. Hosted verification and production behavior are unverified because
deployment was explicitly out of scope. See the [Gray
handoff](../messages/t81_gray_public_legal_pages.txt).

T81 CI-unblock follow-up: reconciled PR #242 with current `main` at
`6a607a4` (merge commit `a98b2f0`). Corrected only the named inherited
Ruff/format findings in `src/sigma/gmail_delivery.py`,
`src/sigma/ui_instance.py`, `src/sigma/cli.py`, and
`tests/gmail_delivery.py`, plus the Pyright narrowing in the email test. The
named-file Ruff check/format, Pyright, and focused email delivery tests pass;
the legal-page Chrome check passes. On this reconciled tree, `./sigma test`
still exits 1 on a startup-warning assertion in `tests/tooling.py` and
formatting in current-main `src/sigma/cloud_auth.py`, both outside this
follow-up's authorized fix scope. Hosted verification remains unverified.
See the updated [handoff](../messages/t81_gray_public_legal_pages.txt).

## T81 remaining feedback and privacy increment (2026-10-26)

Continues T81 after invitation PR #225 merged at
`f45ada5aac3380a5b02e6d7727f0790e90e4a38e`, starting from current `main` at
`e62d808` (including PR #227). Added durable feedback records in the private
cloud-auth SQLite database, optional validated contact email, signed-in
verified-account attribution, a five-per-24-hour per-account/browser rate
limit, and admin-only review/status updates. Feedback is not sent to AI or mail
providers. Feedback entry is available in About for hosted signed-in users and
on signed-out guest/denied screens; Request Invitation remains on Access Not
Granted.

Added an unauthenticated `/privacy` page linked at feedback and invitation
collection points. It identifies itself as proposed version 1.0 and remains
subject to Brian's approval before publication as operative policy. The
proposed text and repository evidence are in
[PRIVACY_NOTICE_DRAFT_v1.md](PRIVACY_NOTICE_DRAFT_v1.md). Open retention, deletion,
contact, jurisdiction, infrastructure-log, backup, and provider-policy
questions are listed there; no unsupported guarantees are made.

`./sigma test` passed all scenarios, Ruff check/format, Pyright (0 diagnostics),
frontend typecheck, and production build. Real Chrome passed public privacy
access without auth calls, signed-out and signed-in feedback success, retained
feedback after a simulated 503, denied-screen invitation placement/privacy
link, responsive layout, and administrator feedback/invitation review.
No production deployment, live email, Google/OAuth call, or paid provider call
was performed. Hosted deployment requires `SIGMA_INVITATION_SMTP_USERNAME` and
`SIGMA_INVITATION_SMTP_PASSWORD_FILE`; the approved credential is not
provisioned or tested here. Implementation was validated at
`756ae45b866f353e307596f5770dcd37ad06aeaa` on `green/t81-feedback`. The branch
is pushed; PR creation is pending a refreshed GitHub connection after the PR
connector returned 401 `token_revoked` (`gh` is unavailable). Issue #81 remains
open. See the [Green handoff](../messages/t81_green_feedback_privacy.txt).

## Issue #215 — request-toast expiry (2026-10-26)

Request-error toasts now expire after 60 seconds, slide downward before removal,
and collapse their stack slot so remaining toasts reflow smoothly. Each toast
has an independent timer; manual dismissal remains available, reduced-motion
users receive immediate expiration, and the existing four-toast/mobile width
limits remain intact.

Seven fake-clock Node tests cover timing, independent lifetimes, manual and
simultaneous dismissal, burst/cleanup behavior, reduced motion, and the CSS
exit contract. A real-Chrome check verified the downward transform, stack
reflow, reduced-motion mode, and 390px layout. The complete `./sigma test`
passed, including Ruff, Pyright, frontend typecheck, and production build.
After reconciliation, GitHub Actions passed SIGMA verification, Research
Outcome browser acceptance, and T92 Recent Projects browser acceptance on
`bdfe0acd2ae867866637e309648b314376140434`; coordinator correction `d625216`
is preserved. No provider calls or research projects were involved. See [PR
#221 (T215)](https://github.com/bkramerext/sigma/pull/221) and the [Blue
handoff](../messages/blue_t215_r4r.md).

## Issue #217 administrator contact (2026-10-26)

Updated the public administrator contact example to
`zetacontinuation@gmail.com`. At this Issue #217 snapshot, the denied-access
link built a `mailto:` draft from the configured contact; T81 supersedes it
with the server invitation workflow described below. The
About dialog and privacy copy contain no administrator contact address, and
there were no administrator-address email templates or static contact links to
update. Generic example addresses in deterministic auth/deployment fixtures and
the unrelated Caddy TLS operator contact remain unchanged.

The current auth implementation had tied the public contact value to the
non-revocable bootstrap identity. It now keeps an established administrator's
email and Google subject binding from the auth database authoritative after a
contact change. New installations still use the configured address to establish
their first administrator. A regression test changes the contact after binding,
confirms the original admin session/role and management identity remain intact,
and confirms the new contact cannot claim admin. No OAuth settings, account
grants, secrets, or stored identity data were changed.

Verification at the Issue #217 snapshot: `tests/cloud_auth.py` passed (18 tests). Real Chrome confirmed the
configured contact in the invitation `mailto:` link and no horizontal overflow
at 1280px and 390px. `npm --prefix frontend run typecheck` and
`npm --prefix frontend run build` passed (the build retains its existing large
chunk advisory). The first `./sigma test` on the ticket's starting `main`
reported the then-current unrelated Ruff B023/format findings in
`browser_checks/model_availability.py`. After current `main` advanced and its
Ruff repair was merged into this branch, `./sigma test` passed every scenario,
Ruff check/format, Pyright (0 diagnostics), frontend typecheck, and production
build. The broader `browser_checks/t22_access_denied.py` stops at its stale
“Explore Demo” guest-link assertion; current guest Home says “Explore SIGMA”.
The focused invitation Chrome check passes. No paid provider calls,
production configuration changes, or live OAuth occurred.

## T86 — README integration preparation (2026-10-26)

Reconciled the recovered README draft against current `main`. The README now
describes current local product behavior and limitations, setup, optional AI
configuration, the current `SIGMA_CLOUD_ADMIN_CONTACT_EMAIL` local Google
administrator bootstrap, and links to the existing Product Rationale and
primary product/engineering documentation. Setup and OAuth details were
checked against `src/sigma/cli.py`, `src/sigma/ui.py`,
`docs/CLOUD_DEPLOYMENT.md`, and `deploy/env.example`. The administrator
bootstrap wording preserves the current behavior for fresh and existing local
auth databases. WOLF was not modified.

Two separate placements identify the pending owner-provided screenshots:
SIGMA Home and a Riemann Hypothesis investigation. Neither image was generated
or substituted. Brian's delivery of those two screenshots remains a documented
follow-up dependency; no credentialed Google sign-in was exercised.

Verification on the T86 branch: `./sigma setup` passed; `./sigma start` with
`SIGMA_CLOUD_ADMIN_CONTACT_EMAIL` unset reached ready state, frontend and API
health URLs returned HTTP 200, and `./sigma shutdown` completed. A local README
link scan found 14 Markdown links and no missing local targets; `git diff
--check` passed. `./sigma test` passed all scenarios, Ruff, formatting, Pyright
(0 diagnostics), frontend typecheck, and production build (with the existing
chunk-size advisory). No paid provider calls or live OAuth operations were
performed.

## Issue #209 — Current Understanding strategy suggestion (2026-10-26)

Replaced the “Continue from Saved Evidence” control with an explicitly
requested **Suggest a Strategy** action nested after the Current Understanding
synthesis. The new provider request uses the selected project/account binding,
existing billing and cloud usage accounting, an enforced 48,000-character
context bound, the cross-session Current Understanding projection, bounded
relevance-selected session evidence, and all saved strategies including
disabled/removed ones. It returns at most one copy-only Markdown suggestion or
a no-additional-strategy result. Suggestions use the safe existing Markdown
renderer and standard copy-control styling; no project strategy or session
record is changed. Removed the continuation proposal/approval API routes while
retaining read-only compatibility for historical continuation packets and
session dispatch.

Verification: `tests/proposals.py` passed against a deterministic mock
Responses transport, including strategy-context input, one Markdown result, a
null/no-new-strategy result, no project.json mutation, and the removed legacy
proposal route returning 404. Existing continuation/history tests passed in
the full suite. Focused Ruff check/format, Pyright (0 diagnostics), frontend
typecheck, and frontend production build passed. Real Chrome exercised the
suggestion button, rendered block, collapse, clipboard contents, no dialog,
and unchanged strategy count using a mocked API response; the broader
`browser_checks/current_understanding.py` then failed in its pre-existing
evidence-focus assertion before completing the full navigation/export pass.
No real provider call was made.

The final `./sigma test` run reached repository-wide Ruff checks after all
scenarios passed, then exited 1 on unchanged `browser_checks/model_availability.py`
(B023 loop closure and existing formatting). A preceding run also reported
`tests/research_sessions.py` nonzero; its standalone rerun and the subsequent
full-suite run both passed. The full command skipped its frontend build after
the Ruff failure; `npm --prefix frontend run build` was run separately and
passed. This is R4R with that baseline Ruff defect and the unrelated browser
evidence-focus failure recorded for review, in [PR #213](https://github.com/bkramerext/sigma/pull/213).

## Current state — research effectiveness (2026-10-26)

Engineering tests and deterministic dry-runs establish implementation
properties only; they do not establish research superiority. T146 preserved
one authorized, same-model paired live case on a single scheduling problem.
Both arms found the exact answer; SIGMA's Skeptic added no substantive
correction, and the single-role baseline later weakened a correct result after
an invalid self-critique. This is a descriptive within-session observation, not
a test of cumulative cross-strategy research. Full records and limitations are
in the [T146 assessment](evaluations/increment_22/exports/trial_20261025/assessment.md).

The blinded unfamiliar-task comparison of cumulative Investigator/Skeptic
research across multiple strategies and saved sessions remains **not frozen and
not run**. Its current design, proposed $15.60 / 192-call maximum, scoring plan,
failure handling, and freeze/authorization gates are in the
[T114 cumulative preregistration](evaluations/T114_CUMULATIVE_PREREGISTRATION.md).
No paid or live provider call is authorized by that document. The earlier
public six-task dry-run and T146's one-task comparison are not substitutes.
Same-model Investigator/Skeptic agreement is not independent verification.

The bounded maintainability review records `research_sessions.py` at 8,666
lines and recommends staged, behavior-preserving extraction only if separately
prioritized; no wholesale refactor was performed. See the preregistration for
module seams and current blockers. Cloud acceptance status is recorded in its
dated entries below and is separate from research-quality evidence.

T114 engineering verification: the cumulative planner's deterministic,
budget, pairing, and failure-retention checks pass; focused Ruff and Pyright
pass. `./sigma test` reaches all scenarios and Pyright (0 diagnostics), but
exits 1 at pre-existing Ruff/format findings in
`browser_checks/model_availability.py`; consequently the frontend production
build is skipped by the runner. Frontend typecheck passes. No browser workflow
or new SIGMA project/session was exercised; the existing T146 exports remain
the actual live paired evidence. No provider call was made.

## T129 initial GCE preview deployment (2026-10-26)

Deployed release `e1ef8db8ea6c15bcb79ad9c8d06e8e5f6f4527f3` to
`sigma-gce-01` in `sigma-research-prod` / `us-west1-b` through authenticated
IAP. The VM checkout, `/etc/sigma/deploy.env` release pin, and backend/frontend
image source labels all identify that SHA. The installed host preflight was
updated from the release and includes PR #199's rootless Docker invocation fix.

Before deployment, the retired `SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL` line was
removed after confirming its identity matched the existing
`SIGMA_CLOUD_ADMIN_CONTACT_EMAIL`; the contact line was preserved unchanged.
The original protected file is backed up at
`/var/lib/sigma/releases/deploy.env.before-e1ef8db8ea6c15bcb79ad9c8d06e8e5f6f4527f3`
(`root:root`, mode `0600`). A pre-deployment snapshot of the attached
`sigma-state` disk reached READY as `sigma-state-preview-20261026-063909`.
It is a one-off recovery point without the scheduled-backup labels. The first
documented uppercase-T/Z snapshot name was rejected by GCE's resource-name
rules; no resource was created by that rejected attempt.

The T128 host-readiness gate passed all rows after installing the corrected
checker. Production preflight passed all 23 rows before startup and again after
startup. `deploy/deploy-gce-release.py ... --initial` built and started the
exact release; `sigma.service` and host Caddy are active, and backend,
frontend, and edge containers report healthy. The existing Caddy hostname
block was still serving a static readiness page, so it was backed up at
`/var/lib/sigma/releases/Caddyfile.before-e1ef8db8ea6c15bcb79ad9c8d06e8e5f6f4527f3`
and changed only to the documented loopback reverse proxy; Caddy validation
and reload passed.

The public endpoint probe passed DNS A, private-port closure, HTTP-to-HTTPS
redirect, trusted HTTPS root, SPA deep link, and hosted API readiness. Local
headless Google Chrome loaded the live page with the SIGMA title, app root,
semantic main element, and rendered body text. No paid inference, IAM change,
DNS/firewall change, reboot, or destructive storage operation occurred. The
initial probe exposed the missing host-Caddy route; after that documented
route was installed, the full probe passed. One manual preflight invocation
also omitted `--repository /opt/sigma/current` and therefore looked in the
installed checker's libexec directory; the documented invocation passed, and
the service remained stopped only until that correct gate was rerun.

Formal acceptance is still pending tomorrow. No OAuth sign-in or two-identity
isolation test, research runtime execution, paid provider call, reboot recovery,
or restore drill was performed. The recurring backup scheduler is not
configured; the one-off snapshot is the current recovery point. No tests were
run as part of this deployment operation.

## T88 Google account and sponsored model access (2026-10-26)

Implemented on ticket branch red/t88-google-sponsored-auth from current
main (2c409e6). The canonical scope is [issue #88](https://github.com/bkramerext/sigma/issues/88).

Hosted guests now land on a distinct Explore-only entry and can browse the
public saved Demo without mounting the inference UI. Protected APIs still
require the verified Google session. Invited accounts persist a subject-keyed
account record containing verified email, current role/access, the existing
subject-derived workspace ID, model access mode and latest server-checked model
connection state. Sponsorship eligibility is a separate revocable flag; spend
and held/unknown usage remain in T99's persistent ledger. Grant role/revocation
changes synchronize account authorization without resetting usage. Admins use
the same budget admission as regular users.

The existing account/model controls are combined into a two-line pill and one
dialog. In local Google-auth mode, mounting the authorized app automatically
checks its existing personal model connection. Hosted mode checks the server's
sponsored credential against the provider model catalog (no research prompt)
and shows checking, reachable, unconfigured, rejected, unavailable, retry and
exhausted-budget states. It does not silently fall back to personal credentials.
Sign-out clears the browser's remembered project pointer. Existing visual
tokens and dialog conventions are reused.

Integration findings: T22.2's verified OIDC, invitation/admin grant, session,
and denied-account paths remain authoritative and are reused. T174's existing
subject-keyed durable workspaces and path checks remain authoritative and are
reused. T99/T99.1's server credential selection, persistent admission ledger,
usage reconciliation, and budgets remain authoritative and are reused. T43.2's
multi-account browser acceptance now asserts the integrated account/model
control. One pre-existing design boundary remains explicit: T22.2's opt-in
local-auth mode deliberately keeps the traditional shared local project root;
private per-subject workspaces are provided by hosted mode. Changing that local
data model would conflict with T22.2's promise to preserve local projects, so
the hosted isolation path is what the two-user acceptance exercises. Hosted
personal ChatGPT OAuth remains forbidden per T172; hosted model use is the
sponsored server credential only.

Verification on this branch: tests/cloud_auth.py (17 tests),
tests/cloud_research_sponsored_api.py, tests/cloud_research_api.py,
tests/cloud_workspaces.py, real Chrome browser_checks/t23_1_google_signin.py
(guest Demo, member/admin switch, isolated workspaces, two-line status, sponsor
connection success/provider outage and auth rejection/retry, budget exhaustion,
sign-out and denied account), frontend typecheck/build, Ruff and Pyright. The
The final `./sigma test` passed every repository scenario, static analysis,
frontend typecheck and production build. The initial full-suite attempt found
an existing Ruff B023/format defect in browser_checks/model_availability.py;
its test lambda now binds the response status explicitly. No external OAuth,
GCP changes, paid inference, secrets, or live provider requests were used;
Google and provider boundaries were deterministically mocked. Live hosted
OAuth, real two-account deployment isolation, and production provider
connectivity remain unverified.

See [T88 worker handoff](../messages/t88_red_google_sponsored_auth.txt) for the
requirement evidence and exact final verification results.

### T88 continuation — combined sign-in and hosted connection isolation

Continued the preserved Green entry and invitation UI on top of merged T200
(`48fe9a1`). The entry dialog presents Google sign-in, Invite Me, and Guest.
Invited Google accounts can select a personal connection or, while eligible
with remaining allowance, explicitly choose SIGMA's sponsored connection. The
dialog displays remaining allowance and hides the sponsored action at zero.
Guest sample-project access and the existing local ChatGPT sign-in remain
available. Settings preserve each hosted account's connection selection so
users can switch without deleting personal authentication.

Hosted account state is selected by verified Google subject. Its future
personal credential store is under a hashed-subject server directory, distinct
from the sponsor store. Deterministic tests verify two-user isolation, token
refresh rotation, selected-connection routing, switching, exhaustion, and
failure recovery. Sponsored requests continue through T200's sponsor
connection and T99's existing allowance, budget, reservation, concurrency,
failure-hold and reconciliation safeguards. Personal and sponsored routing
never borrow credentials from each other.

Hosted personal inference remains explicitly unavailable. No supported
OpenAI plan-access authorization path has been established, and the website
OAuth client is not treated as proof of inference permission. No local-helper
credential transfer was implemented. The exact adapter boundary and external
dependency are documented in
[T88 hosted personal connection boundary](T88_HOSTED_PERSONAL_CONNECTION.md).
No production change, credential transfer, OAuth call, or paid provider call
was made.

Verification: `tests/cloud_personal.py` (3), `tests/cloud_auth.py` (29),
`tests/cloud_sponsor.py` (8), hosted research/API funding and authorization
scenarios, deployment packaging, Ruff, Pyright, frontend typecheck/build, and
real Chrome `browser_checks/t23_1_google_signin.py` all passed. `./sigma test`
passed end to end, including the new subject-isolation suite and production
build. The build emits the existing advisory for a JavaScript chunk over
500 kB. The first full-suite attempt before explicit sponsor test setup was
corrected failed two stale expectations that relied on the old implicit
sponsor selection; the corrected focused suites and final full suite passed.
There are no remaining known baseline failures. See the [Green T88 handoff](../messages/t88_green_combined_signin.txt) for exact branch and PR details.

Integrated current `main` after PR #246 merged at
`bea2108ae08d7f33f9132f5e2d3e06713ee52b44`. Resolved the overlaps in the AI
provider, Home entry/catalog, and workspace identity changes while preserving
T88's verified-subject connection routing and PR #246's Guest workspace,
samples, Guest Play dialog, and sign-in messaging. A responsive Home layout
keeps the T88 entry actions and Guest sample navigation accessible. Focused
account/sponsor/research tests, T88 and Guest samples/Play real-Chrome checks,
and the full `./sigma test` all pass on the integrated tree. Hosted personal
ChatGPT inference remains unavailable pending a supported authorization path;
no credential workaround or paid provider call was used. See the updated
[T88 handoff](../messages/t88_green_combined_signin.txt).

## Issue #98 integrated local browser acceptance (2026-10-25)

Accepted the current integrated local browser workflows against `origin/main`
`dd23fec` using installed Google Chrome and isolated fixture-backed API data.
T95 `browser_checks/t95_paused_session.py` passed pause explanation, reopen,
guarded resume error, and 1440/390px layout. T125
`browser_checks/t125_saved_paper_library.py` passed fixture-backed saved-paper
text and PDF downloads, inline PDF, escaped preview, version-scoped removal,
and mobile layout. `browser_checks/saved_paper_library.py` also passed TeX/PDF
headers and payloads, inline PDF, disclosure, deletion, and responsive layout.
PR #194's text download behavior is present and passed.

T92 `browser_checks/t92_recent_running.py` passed Recent's idle/running/stopped
polling and reload behavior at 1280/390/320px. The sample Outcome and report
workflow passed `browser_checks/nonconsecutive_sample.py`: all five saved
Outcomes were inspectable, Report Export returned 50,057 characters, mobile
widths had no overflow, and Chrome reported no page errors. The guarded resume
failure in T95 provided a real-browser error-state check. `tests/project_reports.py`
and the lifecycle/API scenarios also passed in `./sigma test`.

Acceptance found one narrow accessibility defect: saved-paper disclosure
buttons exposed their changing Expand/Collapse instruction only through the
tooltip, not their accessible name. Added a matching dynamic `aria-label` in
`frontend/src/main.tsx`; T125's existing accessible-name assertion now passes.
No other production-critical browser defect was found in the exercised flows.

Verification: after `npm ci --prefix frontend`, T95, T125, T92, Home Recent's
live-update check (`browser_checks/home_running_status.py`), and the sample
Outcome/report check passed in real Chrome. The combined
`env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed all scenarios,
Ruff check/format, Pyright (0 diagnostics), frontend typecheck, and production
build (existing large-chunk advisory). One initial full-suite run reported
`tests/storage.py` sample-open failure; the isolated storage rerun passed, and
the subsequent complete suite passed. Legacy `browser_checks/recents.py`
still asserts an obsolete manually injected Running shape, and
`browser_checks/t17_8_saved_session.py` expects an older authored-claim Outcome
projection; their current equivalents above passed. No live OAuth, paid model
calls, hosted identity, or deployment infrastructure was used. Follow-up fix:
[PR #197](https://github.com/bkramerext/sigma/pull/197), based on current
`main` after merging PR #196.

## T128 live GCE host readiness (2026-10-26)

Authenticated GCE access is available in this session. `gcloud auth list` showed
the active personal owner account; project `sigma-research-prod` lists
`sigma-gce-01` as RUNNING in `us-west1-b`. The VM has Ubuntu 24.04 amd64, OS
Login enabled, external IPv4 `136.66.128.82`, and runtime service account
`sigma-runtime@sigma-research-prod.iam.gserviceaccount.com`. Current IAM grants
on this account include project `roles/owner`, `roles/compute.osAdminLogin`, and
`roles/iap.tunnelResourceAccessor`; this is too broad for routine worker use.

Using PR #195's current-main preflight as the basis, live
`sudo ... gce_preflight.py --host-readiness --json` first exposed a false
failure: Docker was invoked as root with `--host /run/user/1001/docker.sock`,
which Docker parsed as TCP `localhost:2375`. Running it as `sigma-sandbox`
with the explicit `unix:///run/user/1001/docker.sock` endpoint fixed the rootless
checks while preserving inherited-context clearing. The fix is in
[PR #199](https://github.com/bkramerext/sigma/pull/199). The reviewed script was
copied temporarily to `/tmp`, run read-only as root, and removed. The live
host gate exited 0: all rows PASS, including Ubuntu, UUID/fstab mount,
`nodev,nosuid,noexec`, private root ownership and sandbox denial, active/enabled
system Docker and sandbox services, linger, daemon separation, rootless mode,
socket policy, both Python/Sage images, systemd syntax and guarded service
unit. The dedicated daemon reports `seccomp`, `rootless`, and `cgroupns`; both
images inspect successfully as the sandbox user. No application-path runtime
probe was run because it requires an active backend; `sigma.service` remains
disabled and inactive as required. Its unit has Docker/sandbox requirements,
`RequiresMountsFor=/srv/sigma-state`, and guarded preflight startup.

The installed checker and `/opt/sigma/current/deploy/gce_preflight.py` still
have SHA-256 `2a084da34a0e2969853e7ef21d7464e4bd18c71e15697c1eb8bcc8c1916b125e`;
the audited main source before this fix was `8540b1af17a90b2f69685c328b7932dda01405c2af096da6af2c17a3a893b67b`.
No host copy was replaced. The installed checker will continue to false-fail
rootless daemon/image rows until the reviewed fix is merged and deployed.

The attached `pd-balanced` state disk is non-auto-delete, 30 GiB, mounted at
`/srv/sigma-state` from UUID
`28ef67cb-4da8-46e7-9a8b-dce0470153a5`, `ext4`, `root:root 0700`; 28 GiB was
available. The sandbox user cannot read the mount root. The deployment cost
estimate currently assumes a 200 GiB state disk and an `e2-standard-4`, while
the VM has an `e2-standard-2`; reconcile that sizing before sustained hosted
research. No disk resize or VM change was made.

Effective firewall output for this VM's `sigma-vpc` network and tags showed
only IAP SSH from `35.235.240.0/20` to `sigma-iap-ssh` and public TCP 80/443 to
`sigma-web`. The effective 80/443 rule is `0.0.0.0/0`; no effective rule
exposes TCP 22 publicly or ports 8000, 5173, 2375, or 2376. DNS A resolves to
the VM address and has no AAAA record. HTTPS returned HTTP/2 200 with verified
TLS from Caddy; HTTP returned 308. This is the 25-byte readiness page, not
proof of a running SIGMA application.

The production gate was also run read-only using the reviewed current-main
checker. It returned FAIL because `/etc/sigma/deploy.env` still includes the
retired `SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL` setting; the current runbook says
to remove that line and retain the exact prior identity in
`SIGMA_CLOUD_ADMIN_CONTACT_EMAIL`. The checker read the protected env file's
settings but emitted no values; key names were separately listed without
values, and secret-file contents were not accessed. The deployed
preflight/configuration was not changed and the app was not started.

The current main's open [PR #198](https://github.com/bkramerext/sigma/pull/198)
adds a repository Codex launcher and read-only worker connectivity checker.
That launcher does not grant GCP permissions; PR evidence says the persistent
worker execution contexts have not yet been verified. This session's successful
`gcloud` and IAP access proves only this local authenticated context.

Least-privilege access: create a dedicated worker identity and remove project
Owner/OS Admin from routine use. For a limited SSH fallback, scope OS Login and
IAP tunnel permissions to this VM and allow only a root-owned fixed-argument
read-only preflight wrapper through sudoers. To remove SSH commands entirely,
a host timer can publish only sanitized preflight JSON to a dedicated Cloud
Logging view; grant the worker `roles/logging.viewAccessor` on that view alone.
Avoid OS Config Exec access for routine workers because its policy scripts
execute on the VM. Google documents [OS Login role behavior](https://docs.cloud.google.com/compute/docs/oslogin),
[IAP TCP forwarding](https://docs.cloud.google.com/iap/docs/using-tcp-forwarding),
[view-scoped Logging access](https://docs.cloud.google.com/logging/docs/access-control),
and [OS policy Exec resources](https://docs.cloud.google.com/compute/docs/osconfig/rest/Shared.Types/OSPolicy#Exec).
No IAM or host configuration was changed.

After rebasing onto current `main` `3cba4e1`, `uv run python
tests/gce_host.py` passed 21 tests and
`env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed all scenarios,
Ruff, formatting, Pyright (0 diagnostics), frontend typecheck and production
build. The build emitted the existing large-chunk advisory. The initial suite
attempt found Ruff formatting and missing frontend `tsc`; after formatting and
`./sigma setup`, the full rerun passed. No browser check was relevant to this
host-preflight change. No paid calls, service start, reboot, or production
configuration change occurred.

## Issue #186 single administrator/contact setting follow-up (2026-10-26)

Follow-up to [PR #187](https://github.com/bkramerext/sigma/pull/187) per the
updated product requirement: `SIGMA_CLOUD_ADMIN_CONTACT_EMAIL` is now the single
configured address for invitation contact and initial administrator identity.
Its first verified Google sign-in binds the email to that immutable Google
subject and receives admin; later admin authorization still requires both the
configured address and the bound subject. Nonmatching email/subject identities
remain denied. The old variable is no longer read or accepted by active auth or
deployment configuration; regression tests verify that stale deployment files
using it are rejected.

Documented the upgrade path in Cloud Deployment: remove the old line and set the
single setting to the exact prior administrator address to preserve the existing
database's subject binding. Changing the address does not transfer the stored
binding. Local development, Compose, GCE preflight, browser setup guidance, and
auth regression coverage now use the single setting. Focused cloud auth (17),
tooling, deployment-package, and GCE host/preflight (18) checks passed. The first
full-suite run found two Ruff format differences; after formatting,
`env -u SIGMA_CLOUD_ADMIN_CONTACT_EMAIL ./sigma test` passed all scenarios,
Ruff check/format, Pyright (0 diagnostics), frontend typecheck, and production
build (existing large-chunk advisory). A focused real-Chrome setup-panel check
passed and confirmed the single setting is shown without starting OAuth. The
broader T43.1 Chrome script stopped earlier at its unrelated existing artwork
credit text assertion. No provider calls, live production configuration, or
cloud resources were touched.

## Issue #186 bootstrap administrator versus admin contact (2026-10-26)

Historical entry for the initial review; its two-setting recommendation was
superseded by the follow-up product requirement above.

Reviewed the auth service and deployment preflight. `SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL`
is an authorization input: the first verified Google identity matching it is
bound to the configured email and granted admin; later sign-ins require both
that email and the bound Google subject. `SIGMA_CLOUD_ADMIN_CONTACT_EMAIL` is
only invitation-contact display metadata and grants no access. Replacing or
falling back to the contact would change which account can claim the initial,
non-revocable administrator role. Therefore the settings remain distinct; they
may be equal only when the approved contact is intentionally that same Google
account. No authorization code or live production configuration was changed.

Updated the deployment env example and runbook to state the identity distinction,
and added a cloud-auth regression proving the contact account is denied and
does not receive an authenticated session/workspace. `tests/cloud_auth.py` (17
tests) and `tests/gce_host.py` (18 tests, including deployment env preflight)
passed. The first `./sigma test` run reached Ruff format and reported only the
new test's formatting. After formatting it, `./sigma test` passed all scenarios,
Ruff check/format, Pyright (0 diagnostics), frontend typecheck and production
build. The build emitted the existing large-chunk advisory. No browser check
applied to this auth configuration and documentation change. No provider calls,
costs, or live production operations occurred.

## Host Caddy and GCE Compose port contract (2026-10-26)

Kept host Caddy as the GCE public HTTPS endpoint. `deploy/compose.gce.yaml`
now overrides the Compose edge publication to a single
`127.0.0.1:18080:80/tcp` binding and runs that edge in HTTP mode. Its upstream
scheme is explicitly HTTPS so the application receives the production origin
scheme. Local Compose retains its configurable 80/443 defaults. The exact host
site block is in `deploy/host-caddy.Caddyfile`; GCE preflight now rejects any
other published port, non-loopback bind, or additional edge publication.

Fetched T128 merge `37b2433e90da10afe09c478284cbee6aea44a005` before final
verification. The stale systemd mount assertions were corrected there; I did
not modify Red's files. Focused GCE port-contract/preflight checks passed, as
did the deployment package, GCE host (18 tests), host monitor (9 tests), and
release-image (3 tests). `./sigma test` passed all scenarios, Ruff check and
format, Pyright (0 diagnostics), frontend typecheck, and frontend production
build (with the existing large-chunk advisory). Docker Compose v2 is
unavailable here, so I could not render the merged Compose configuration
locally. No live VM, GCE, or deployment operation was performed.

## T128 GCE host readiness and runtime security review (2026-10-26)

**Readiness: BLOCKED for production activation.** Reviewed current `main`
(`8e8d979`), the host preflight/installer, state disk path, systemd services,
production Compose policy, runtime-check command, and operator runbooks. Source
inspection supports the intended boundaries: a separate rootless
`sigma-sandbox` daemon, unprivileged isolated research containers, and backend
state mounted only from `/srv/sigma-state/auth`. These are not live-host
observations. No SSH, cloud/provider calls, installer, service activation,
reboot, or infrastructure change occurred. Supplied host status, IP, DNS, and
TLS facts were not independently checked.

Reconciled the three stale deployment assertions in `tests/deployment_package.py`,
`tests/gce_host.py`, and `tests/host_monitor.py`: current `sigma.service` uses
`RequiresMountsFor=/srv/sigma-state`, with explicit Docker and rootless-sandbox
`Requires`/`After` ordering. The production package also defines its own Caddy
edge publishing 80/443 on all interfaces by default, which conflicts with the
operator-reported active host Caddy. Production must select one edge or add a
reviewed loopback upstream mode before activation. Detailed verified facts,
limits, and pending read-only commands are in
[`T128 host readiness`](T128_HOST_READINESS.md).

Baseline `./sigma test` completed all scenarios through static analysis but
failed on the three stale assertions and absent frontend `tsc`; the frontend
build was skipped after failures. After correcting the assertions and running
`npm ci --prefix frontend`, focused deployment-package, GCE-host (17 tests),
and host-monitor (9 tests) checks passed. Final `./sigma test` passed all
offline scenarios, Ruff, formatting, Pyright (0 diagnostics), frontend
typecheck, and production build (existing large-chunk advisory). Local Docker
was not rootless; Compose v2 and `systemd-analyze` were unavailable. No real
browser check applied to this configuration/documentation change. No provider
calls or costs occurred. Corrections and the readiness record are in
[PR #181](https://github.com/bkramerext/sigma/pull/181).

Integration follow-up: fetched T129 merge `7d4898733690fa17931e7f2c86aa92b03317ea79`
and merged current `main` into the T128 branch without conflicts. The integrated
diff was limited to T128 docs/tracking and the three mount assertions. T129's
release builder, requested-SHA verification in `start-gce.sh`, provenance
message, and release/storage tests are unchanged from current `main`. Focused
deployment, GCE host (17), host monitor (9), release-image (3), and storage
checks passed. `./sigma test` passed all offline scenarios, Ruff, formatting,
Pyright (0 diagnostics), frontend typecheck and production build (existing
large-chunk advisory). No GCE or deployment services were touched.

## T171 GCE host readiness audit (2026-10-26)

**Overall: BLOCKED for production start.** The audit began from fresh current
`main` and reviewed T128's preflight, installer, rootless service, UUID state
disk path, Compose security controls, host monitor and operator runbook. T128
still requires actual Ubuntu/GCE acceptance. This assignment did not run the
installer, start production services, make provider calls, change the VM,
provision resources or reboot.

Offline review found that `gce_preflight.py` checked the production Compose
health checks, state bind and rootless socket but did not enforce most runtime
resource and security settings. It could therefore report PASS if limits,
capability drops or `no-new-privileges` were removed. Preflight now verifies
backend/frontend/edge UID and container settings, resource limits, noexec
tmpfs where used, and only edge TCP 80/443 publications. `tests/gce_host.py`
adds the regression: removed PID limits, an unconfined seccomp override, and
published port 8000 are rejected.

`uv run --with pytest python -m unittest tests.gce_host -v` ran 17 host tests:
16 passed, including the new regression; one fails on the coordinator-owned
stale systemd mount assertion. I did not change it or either of the other two
known stale assertions in `tests/deployment_package.py` and
`tests/host_monitor.py`.

`./sigma test` completed every independent step. Its final run reported four
failures: the three known stale mount assertions and frontend typecheck could
not find `tsc` in this clean worktree. Ruff lint, Ruff format (238 files), and
Pyright (0 diagnostics) passed; frontend build was skipped after failures. The
local Docker Engine responded but reported a non-rootless workstation daemon;
Docker Compose v2 and `systemd-analyze` were unavailable, so merged production
Compose rendering and native target unit syntax were not validated here.
Focused final checks are recorded in the T171 PR handoff.

The evidence-backed dispositions and exact later live-host commands are in
[T171 host readiness audit](T171_HOST_READINESS.md). The essential blockers
are actual preflight PASS, current persistent disk identity/permissions,
rootless daemon and container inspect, target runtime probes, and approved
reboot recovery. Installer failure can leave partial host state and needs
inspection before retry.

## T43.2 / issue #66 multi-account sign-in acceptance (2026-10-25)

Reviewed the full issue and current Google OIDC and ChatGPT SIWC implementations.
Added a deterministic ChatGPT regression with two distinct verified fixture
subjects and email labels: connecting/selecting accounts, disconnecting the
active account without clearing the other account's tokens, selecting the
retained account, and reconnecting the first identity in place. Extended the
isolated real-Chrome ChatGPT fixture flow to add a second identity, confirm its
active label after reload, and switch back to the first identity. The fixture
reports zero inference calls and scans browser output for credential-shaped
strings. Existing T131 Chrome coverage separately verifies Google A→B fixture
sign-in, reload, logout, rejected identity, and isolated project workspaces.

Executed Chrome checks used simulated identities and provider callbacks. They
are not real Google OAuth, real ChatGPT OAuth, or hosted acceptance. The full
Google A/B × ChatGPT A/B identity cross-product, Google/ChatGPT sign-out
interaction with distinct approved live identities, browser-level completion
of the ChatGPT cancel button, and hosted OAuth callback remain UNVERIFIED. The
AI auth begin/cancel API endpoints and cancellation state are covered by the
deterministic test. Hosted personal ChatGPT authorization remains blocked by
policy and must not be enabled. The hosted-mode API test continues to assert
the 403 guard; local and hosted identity boundaries remain separate.

`uv run --locked --no-sync python tests/chatgpt.py` passed. Real Chrome passed
`browser_checks/chatgpt.py` against its isolated SIWC fixture and
`browser_checks/t23_1_google_signin.py` against its self-started Google fixture.
`./sigma test` ran on current main before edits and again after the account
isolation/browser changes; both runs report the same three pre-existing failures in
`tests/deployment_package.py`, `tests/gce_host.py`, and `tests/host_monitor.py`:
they expect the previous `srv-sigma\\x2dstate.mount` dependency while current
main's systemd unit uses `RequiresMountsFor=/srv/sigma-state`. No auth tests
failed; Ruff, Pyright (0 diagnostics), and frontend typecheck passed. The suite
skipped its frontend build after the deployment failures; `npm --prefix frontend
run build` passed separately with the existing chunk-size advisory. See
[T43.2 handoff](../messages/t43_2_gray_multi_account.txt) and
[PR #166](https://github.com/bkramerext/sigma/pull/166).


## Issue #117 adversarial review follow-up (2026-10-26)

Reviewed issue #117 against current main `13a63c4` and its full discussion.
The Ubuntu installer test safety defect, Ubuntu `os-release` spellings, and
failure aggregation are already corrected by merged T117; the preflight
`BLOCKED` fixture also passes independently. Ruff lint already covers
`deploy/`, `browser_checks/`, and `docs/evaluations/` with no current lint
findings. Ruff format found 17 existing files outside its gate (16 browser
checks and one evaluation exporter); these were formatted and added to the
format gate with a regression assertion.

`./sigma test` ran all independent checks and reported three failures in
`tests/deployment_package.py`, `tests/gce_host.py`, and `tests/host_monitor.py`.
Each asserts the old explicit systemd mount unit; current main uses
`RequiresMountsFor=/srv/sigma-state`. These deployment test corrections remain
with the coordinator under the accepted T128 handoff and were not changed here.
Pyright and frontend typecheck passed; frontend build was safely skipped after
the earlier failures. The installer was not run, and no cloud or provider
activity occurred. Detailed outputs are in
[`issue-117-red-adversarial-review.txt`](../messages/issue-117-red-adversarial-review.txt).

## T146 Increment 22 authorized live comparison (2026-10-26)

Executed the one owner-authorized OpenAI API comparison after a successful
project-scoped-key Models API lookup for `gpt-6.1-sol` with the configured
project context. The first recorded metadata attempt returned 401; later
metadata lookups succeeded, and both results are preserved. No credential
value was written to the repository. The frozen protocol manifest remained
valid.

The fair coin selected the four-turn single-agent baseline first. It used all
four calls and found a valid makespan-10 schedule and lower bound, but then
adopted a false self-critique claiming the task's eligibility/precedence data
were missing and withdrew its correct conclusion. The production SIGMA
Investigator/Skeptic workflow used two calls in one cycle. The Investigator
found a valid makespan-10 schedule and lower bound, and its isolated Python
enumeration checked 2,016 assignment/order cases. The Skeptic received the
saved work and completed computation, confirmed the result, and stopped
productively without a substantive objection or a second Investigator cycle.
The independent checker confirms the proposed makespan-13 schedule is valid
and the exact optimum is 10. In this case the Skeptic did not materially
improve the result; the one-cycle record demonstrates evidence transfer, not
multi-cycle revision.

Provider usage was 18,586 input and 9,948 output tokens across six completed
Responses. Usage-derived charge at the frozen Standard rates was $0.145100;
the conservative settled-ledger cost was $0.145945, below the $0.67 per-arm
local ceilings and $1.32768 full reservation. Brian confirmed the project's
$1.40 enforced limit. A billing dashboard export was unavailable, so posted
project aggregate spend was not independently observed. No response clipped
or had uncertain usage. Arm times were 79.678 seconds (baseline) and 104.935
seconds (SIGMA); overall elapsed time was 232.236 seconds including the local
setup correction. Full transcripts, raw requests/responses, usage, ledgers,
SIGMA project/session/Outcome, computation, preflight attempts, checker output,
and assessment are under
[`T146 trial evidence`](evaluations/increment_22/exports/trial_20261025/assessment.md).

Reconciled the branch with current `main` at
`6c9ebbb0d588cadc885c724b90ff51420935ba55`, preserving the T128 Cloud unit
change. On the merged tree, `./sigma test` ran through Ruff check/format,
Pyright (0 diagnostics), and frontend typecheck, but exited 1 in three existing
deployment assertions (`tests/deployment_package.py`, `tests/gce_host.py`,
`tests/host_monitor.py`) that still expect the former explicit
`srv-sigma\\x2dstate.mount` dependency. The merged unit instead uses
`RequiresMountsFor=/srv/sigma-state`. Cloud files were not changed for T146.
The frontend production build passed separately; it reports the existing
greater-than-500-kB chunk advisory. The frozen protocol hashes verify, the
credential scan found zero artifact matches, and a SHA-256 manifest covers all
67 evidence files. Final-head GitHub Actions status is pending publication.

On final head `b9c1538958d37607a40cb6145d986a6cc117b26a`, GitHub Actions
confirmed the local finding: SIGMA verification failed in the same deployment
assertion, while Research Outcome browser acceptance and T92 Recent Projects
browser acceptance passed. See the run links on PR #150. No Cloud source or
deployment files were changed in this increment.

T147 is recommended for a narrowly scoped diagnosis, but was not started.
The saved Skeptic output combines `assessment=stop`, `stop_reason=unresolved`,
and `strategy_contribution=solution`, while the coordinator records a
productive stop with an achieved objective and no open obligations. No merge
was performed; PR #150 remains the review boundary.

## T132 Red hosted research and Python/Sage execution audit (2026-10-25)

Started from current `main` at `803a62d` on `red/t132-hosted-research-execution`.
Audited the hosted sponsored API integration and existing deterministic
coverage. Existing suites already join authenticated HTTP proposal, agentic,
conversion, paper, and research-session generation with owner/global usage
accounting, unknown-outcome no-replay behavior, cross-workspace controls,
execution provenance/artifacts, and recovery; Python/Sage tests cover runtime
limits, errors, timeouts, and persistence. Corrected a stale Cloud Deployment
statement that still described these sponsored routes as disabled despite the
current ledger-backed implementation and regression coverage. Added a pure
rootless-mode policy guard and deterministic regression coverage: the
production path rejects non-rootless daemons unless the explicit development
override is supplied.

Added [T132 hosted research acceptance](T132_HOSTED_RESEARCH_ACCEPTANCE.md)
with repeatable offline commands, a no-override target-host rootless runtime
proof, authorized-only hosted workflow steps, interruption/no-retry handling,
and a sanitized evidence record. Linked it from the operations runbook. No
production service, provider, identity, or cloud resource was contacted or
modified. This is preparation, not hosted acceptance.

The local Docker Desktop ARM64 development smoke passed using
`uv run --locked --no-sync python -m sigma.cloud_runtime_check
--allow-nonrootless-dev`: Python and Sage both ran as UID 65532 and reported
network, host sentinel, host state, and daemon socket blocked; artifact and
execution persistence passed; Tectonic PDF compilation and paper snapshot/PDF
hash persistence passed. It explicitly reported `daemon_rootless: false`, so
it does not validate the GCE rootless boundary. Docker Compose v2 is absent on
this workstation; packaged Compose/browser integration did not run. The strict
`uv run --locked --no-sync python -m sigma.cloud_runtime_check` command exited
1 with the expected non-rootless refusal. `tests/deployment_package.py` passed,
and the final `./sigma test` passed all scenarios, Ruff check/format, Pyright
(0 diagnostics), frontend typecheck and production build. Actual rootless GCE,
hosted OAuth/browser, provider-backed generation, and restart acceptance remain
dependent on Brian's host verification and separate owner authorization for
any live provider usage. Implementation commit `4e8111e22a27f4bb5a9319578ebdd30bc5b5941f`
was submitted in [PR #157](https://github.com/bkramerext/sigma/pull/157); no
merge was performed. Elapsed preparation time through PR creation was about
15 minutes.

## T131 Gray hosted Google OAuth acceptance preparation (2026-10-25)

Started from current `main` at `455d752` in an isolated ticket worktree. Audited
the existing Google OIDC callback validation, secure cookie/session behavior,
unauthorized and rejected identity cases, and authorized-to-authorized and
authorized-to-denied account switching. Added deterministic coverage for a
session surviving a fresh client/browser context, logout clearing the secure
cookie and revoking the stored session, and a stale copied cookie remaining
unauthorized. Added the [T131 hosted OAuth procedure](T131_HOSTED_OAUTH_ACCEPTANCE.md)
with the exact production origin/callback, consent/client and secret-handling
requirements, repeatable desktop actions, and evidence record. Linked it from
the runbook and ticket. No production OAuth client, Google Cloud credentials,
IAM, secrets, or UI code were changed; no live authentication or paid provider
call was attempted.

Validation: `./sigma test` passed all scenarios, Ruff check/format, Pyright,
frontend typecheck, and production build. The cloud-auth module passed all 16
tests. A real Chrome local Google-sign-in fixture check was attempted but is
**UNVERIFIED**: its default API port 8001 was not running; pointing it to the
normal local API then failed because the existing script assumes a test-only
authenticated API harness it does not launch. The local app was stopped after
the attempt. This did not contact Google. Hosted desktop acceptance remains
**UNVERIFIED** pending the deployed release, exact saved OAuth settings/secret
delivery, public HTTPS, and owner-authorized admin/member/rejected test
identities. T130 routing/TLS and T129 deployment remain outside this change.
Preparation elapsed approximately 20 minutes; exact handoff SHA and PR are in
[messages/t131_gray_hosted_oauth_preparation.txt](../messages/t131_gray_hosted_oauth_preparation.txt) and
[PR #156](https://github.com/bkramerext/sigma/pull/156).

### T131 browser harness repair follow-up (2026-10-25)

The previously unverified `browser_checks/t23_1_google_signin.py` check now
starts its own loopback API and Vite servers with temporary storage. Its
Google status/login/logout redirects are deterministic browser fixtures; the
test-only identity adapter handles protected API requests. Real Chrome passed
fixture sign-in, reload persistence, logout, anonymous and revoked-identity
401s, rejected-access UI, account switching, per-account project isolation,
and desktop/mobile project-header checks. No Google endpoint, production OAuth
configuration, credential, or paid provider was used. This resolves the local
harness setup gap only; deployed cookie behavior and hosted Google OAuth remain
unverified. See the self-contained command and fixture boundary in
[`browser_checks/README.md`](../browser_checks/README.md). `./sigma test` also
passed all scenarios, Ruff, format, Pyright, frontend typecheck, and production
build. No SIGMA production auth code changed. Implementation commit
`424ca3aa2cac5ba01a35c9dc11e58c1e251c83ae` is on
[`red/t131-google-oauth-harness`](https://github.com/bkramerext/sigma/tree/red/t131-google-oauth-harness)
and submitted R4R, unmerged, as [PR #158](https://github.com/bkramerext/sigma/pull/158).
Elapsed implementation and validation time was approximately 20 minutes.

## T133 Gray cloud workflow and export acceptance preparation (2026-10-25)

Audited current desktop acceptance before adding coverage. T91 already runs
real Chrome against packaged Compose with two simulated identities and covers
project/strategy edits, saved sessions and evidence, report export, compiled
TeX/PDF, backend recreation, fresh-volume restore and workspace isolation. T100
covers persistent-disk browser reload and backend restart; T45 and
`browser_checks/saved_paper_library.py` cover the paper dialog, TeX/PDF UI
downloads, and inline PDF; service tests cover report formats, text rendering,
paper integrity and cloud workspace boundaries. Added the missing explicit
rendered Outcome assertion and packaged-UI downloads for Project Audit, text,
and HTML in T91. Its recovery fixture now stores its archive under the temporary
run directory. Added support for standalone Compose and Buildx to
`deploy/validate-local.sh`, so the packaged acceptance works with Homebrew
Compose on Apple Silicon; temporary recovery volumes are removed after stack
shutdown. The hosted repeatable checklist is
[T133 acceptance preparation](evaluations/t133/README.md).

Validation: after `./sigma setup`, `./sigma test` passed all offline scenarios,
Ruff, format, Pyright (0 diagnostics), frontend typecheck and production build.
`deploy/validate-local.sh` passed: packaged images built, real Chrome verified
project/strategy save and reopen, 5 saved sessions, rendered Outcome, all three
report downloads, real Tectonic compilation, authenticated PDF and TeX hashes,
malformed TeX rejection, backend restart, fresh-volume restore, data hashes and
user isolation. No Google OAuth exchange or inference/provider call occurred.
The full run used fixture identities and is local packaged evidence only.

Hosted acceptance remains **BLOCKED** by T127/T129/T131/T132. No live host,
Google identities, OAuth, or paid paper generation was exercised. A real hosted
paper generation needs explicit provider/budget authorization if no prepared
paper is available. Elapsed preparation time: approximately 35 minutes.


## T129 GCE application deployment (2026-10-25)

Implementation commit `513a207f20198eab089fed0915637f1eead1efcd` is on
[`red/t129-gce-app-deployment`](https://github.com/bkramerext/sigma/tree/red/t129-gce-app-deployment)
and submitted unmerged as [PR #152](https://github.com/bkramerext/sigma/pull/152).

Offline deployment review adds a Caddy edge healthcheck against its local
admin endpoint; the GCE preflight now fails unless backend, frontend and Caddy
all have healthchecks, while Caddy remains ordered after healthy backend and
frontend. Focused package tests pin the GCE state bind to
`/srv/sigma-state/auth`, hosted `persistent_disk` configuration, auth/workspace
paths, app UID/GID ownership, mount guard and systemd Docker/rootless/mount
ordering. GCE preflight tests exercise acceptance and reject a missing edge
healthcheck. Existing storage scenarios cover backend restart, full state-root
backup/restore, Recent-path rebasing and no startup when the persistent mount
is absent.

Validation: focused `tests/deployment_package.py`, `tests/gce_host.py` (16
tests), and `tests/storage.py` passed. Final `./sigma test` passed all offline
scenarios, Ruff, formatting, Pyright, frontend typecheck and production build.
One preceding full run had a transient `tests/storage.py` restore response
failure; an immediate isolated rerun and the final full run both passed. The
local Docker engine reports 29.5.2, but `docker compose version` exits 1
because the Compose plugin is missing; merged Compose rendering, packaged
container smoke and real Chrome checks could not run. No GCE resources, hosted
endpoints, provider calls or secrets were used. Actual deployment SHA, mount
identity/ownership, service health and persistence after container recreation
remain pending Brian's T127 handoff; no hosted acceptance is claimed.

## Green UI tickets #95 and #125 (2026-10-25)

Implemented on one branch, `green/t95-t125-ui`, from current `main` at
`6686e6f`. Before publication, merged updated `main` at `753b99a` (PR #134)
without conflicts; its only change was `docs/OPERATION_RUNBOOK.md`. The work is
split into reviewable commits:

- **#95 paused-session clarity:** the paused lifecycle state now includes a
  nearby explanation and next step. It classifies known context, duration,
  budget, model/connection, project/strategy, restart, and manual-pause reasons
  from `current_action`, `message`, and the latest typed failure/interruption
  fields. Other recorded reasons remain visible verbatim; a missing reason is
  explicitly described as unrecorded. Resume behavior and backend safeguards
  are unchanged. Commits: `1effc46`, `486c8db`, `04b6a75`.
- **#125 saved AI papers:** saved versions appear as a responsive card library
  with title and date/version metadata, per-version TXT and PDF downloads, and
  an inline-PDF new-tab action. Each card expands a collapsed-by-default view
  of that exact saved draft using escaped React text. Removal has an inline
  confirmation, deletes only the selected paper JSON/PDF, and immediately
  updates the list. The TXT route emits the stored paper text as an attachment;
  existing project-owner authorization protects reads and deletion. Commit:
  `597afcd`.

Real Chrome passed `browser_checks/paused_session_clarity.py` (manual pause,
page close/reopen, visible explanation and next step, narrow viewport, safe
resume) and `browser_checks/saved_paper_library.py` (fixture-authored version,
TXT/PDF payloads and headers, actual inline-PDF popup, accessible expansion,
mobile layout, cancellation and confirmed deletion). `tests/papers.py` and
`tests/cloud_workspaces.py` passed. Frontend typecheck and production build,
Ruff check/format, and Pyright (0 diagnostics) passed. The full `./sigma test`
ran twice and stopped at the existing `tests/tooling.py:177` assertion that
expects `stop_servers` once; it was called zero times. The paper and cloud
ownership scenarios were then run directly and passed. The broad legacy
`browser_checks/a17_research.py` also stops later at a stale `12/30 calls`
expectation; its focused pause/reopen behavior passed before that assertion.
No live or paid provider calls or cloud changes occurred. The browser paper
check used only the deterministic local fixture; its one generation is fixture
traffic.

### Manual feedback follow-up (build 85a9efa)

- The UI now calls every resumable interruption **Stopped**, including backend
  guard states that remain `paused` internally for compatibility. Resume is
  available when no other session is active. **Ended** remains terminal and
  does not offer Resume. The stopped-session notice explains the cause and safe
  next step; when no complete Investigator/Skeptic artifact exists, it also
  states: “The session is stopped and has not saved a complete
  Investigator/Skeptic finding. No answer to the project question is
  established yet.”
- Home Recent and Samples entries show **Runnable** only when the project has
  an active, enabled strategy. The label describes project readiness; AI
  connection availability still applies.
- About already closed on backdrop clicks; real-Chrome coverage now checks
  dismissal and focus restoration.
- Real Chrome passed the stopped-session reopen/resume check and the About
  backdrop check. In the broader `browser_checks/recents.py`, the new Runnable
  assertion passed, then the existing scroll-height assertion failed because
  the sample scroller's `scrollHeight` equaled its `clientHeight` (1275).
- A fresh `./sigma test` again reached the existing `tests/tooling.py:177`
  `stop_servers` call-count failure. Focused `tests/recents.py`, frontend
  typecheck/build, Ruff, and Pyright passed.

### Home session activity feedback

Replaced the strategy-eligibility label in Home with inline `· Running` metadata
only for a persisted research session whose status is `running`. Sample
projects no longer claim to be Runnable or Not runnable. `tests/recents.py`
checks both running and stopped session states. Real Chrome verified the
metadata sentence omits Running for a stopped record and displays
`1 strategy · Medium difficulty · Running` for a running record. The broader
recents browser check passed this new assertion, then hit the existing sample
scroll-height assertion; a second run with only that unrelated assertion
bypassed reached the subsequent flaky Back-to-Home detached-element timeout.

I inspected `projects/test2.sigma` directly: its latest saved research session
is `ended`, and its earlier session is `stopped` with no running branches or
steps. It is therefore correct for test2 not to show Running at this moment.
The full `./sigma test` remains blocked by the unrelated existing
`tests/tooling.py:177` `stop_servers` call-count assertion. Frontend production
build, targeted Ruff and Pyright checks, and the focused recents backend test
passed. No provider calls were made.

After the user reported a newly started run missing from an already-open Home
page, I found Recent had only fetched once on mount. It now refreshes visible
Recent metadata every two seconds (and on focus/visibility return), so an open
Home page reflects session starts and stops. Real Chrome
`browser_checks/home_running_status.py` passed the persisted stopped → running
→ stopped transition without reloading. The local app server was restarted
after the test2 run had ended so its backend loaded the updated response field.

The user then requested saved AI paper cards match the session-row disclosure
pattern. Each saved version now has an adjacent disclosure arrow and title,
date/version metadata with Remove on that line, and vertically stacked TeX/PDF
actions on the right that remain visible while expanded. The TeX action now
downloads the saved `.tex` source used to compile the PDF through a dedicated
authenticated route; the older plain-text route remains available. Real Chrome
`browser_checks/saved_paper_library.py` passed the TeX/PDF download, inline PDF,
collapsed/expanded layout and action visibility, metadata/remove alignment,
mobile layout, and confirmed deletion checks against a fresh local fixture.

### Integrated T95/T125 handoff (2026-10-25)

Merged current `main` at `8c3741a`, keeping both the Green UI history and T134
cloud isolation preparation in this status file. `tests/cloud_workspaces.py`
auto-merged; its newer cross-owner no-mutation assertions and the saved-paper
read/download/delete authorization coverage are present together. Removed the
redundant raw `RecentProject.running` field and its status-only assertions;
Home and the API now rely on T92's recovery-aware `research_running` value. The
Home Chrome fixture holds a worker lock while asserting Running, matching a
live session rather than a stale persisted status.

`env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed all steps.
Focused real Chrome checks passed for stopped-session guidance/resume,
live Home Running updates, the saved-paper library, and the simplified LaTeX
dialog. Cloud workspace and recents backend suites passed independently. All
browser/provider paths used deterministic local fixtures; no paid calls or
hosted identities were used. GitHub Actions will be verified on the pushed
integrated head before R4R.
## T134 cloud isolation and privacy acceptance preparation (2026-10-25)

On branch `gray/t134-cloud-isolation`, based on current `main` at `19e5bd7`,
audited existing ownership coverage in `tests/cloud_workspaces.py`,
`tests/cloud_auth.py`, and `tests/cloud_research_api.py`. Added explicit
no-mutation checks for rejected cross-owner strategy creation/removal, verified
the victim strategy remains available, and fixed the T22 desktop browser check
to allow its actual dynamically assigned Vite fixture origin. Added a reusable
hosted A/B privacy matrix, direct-resource probes, sign-in transition and
sanitized evidence template in [T134 hosted acceptance](T134_HOSTED_ACCEPTANCE.md),
linked from the operator runbook. Ticket and deployment checklist now identify
this as offline preparation, with hosted acceptance blocked on T131/application
deployment.

Validation: `./sigma test` passed all offline scenarios, Ruff, format, Pyright
(0 diagnostics), frontend typecheck and build. The full run included cloud auth
(15 tests), two-workspace isolation/restart/restore, cloud research/API
accounting and fake-provider isolation checks. `uv run --locked --no-sync
python tests/cloud_workspaces.py` passed after the final focused test change.
`uv run --with playwright python browser_checks/t22_private_workspaces.py`
passed with real Chrome using disposable deterministic principals and local
storage. The first browser run exposed the missing dynamic-origin fixture
allowlist; the test launcher was corrected and rerun successfully. No live
Google identities, hosted endpoints, OAuth exchanges or provider calls/costs
were used. This does not establish hosted acceptance.

Hosted evidence remains UNVERIFIED and blocked until T131 and application
deployment are ready, owner-authorized Google test identities are available,
and any provider-backed session/usage path has separate authorization. No
production IAM/OAuth settings or behavior changes were made. Preparation took
approximately 30 minutes at handoff; PR details and exact commit are in the
linked T134 message file.

## T136 monitoring and recovery preparation (2026-10-25)

On branch `gray/t136-cloud-ops-recovery`, based on current `main` at
`690fff6`, added an independent read-only 15-minute systemd host monitor and
installer without changing Red's host/application units. It requires the exact
`/srv/sigma-state` mount and verifies the mounted block device resolves to
`google-sigma-state` before reading capacity. It detects low free space/inodes,
failed dependencies and unhealthy Compose containers, backup failure/staleness,
missing last-success READY snapshots, and fewer than 14 managed READY points.
Failures include safe actionable details in the local journal and a critical
journal event; no remote alert path is configured. Added a guarded release
rollback helper requiring explicit verified-backup and schema-compatibility
assertions; it changes only `SIGMA_RELEASE`, keeps volumes/state untouched, and
restarts the prior release when candidate preflight/start/health checks fail.

Updated the operator runbook with install/diagnosis, reboot validation,
reservation semantics, rollback requirements, failure limitations and live
acceptance gaps. T136 status remains **offline preparation only**. The hosted
reboot/restart test, actual disk thresholds and identity, production monitoring
timer, external alerting, 14-point snapshot inventory, HTTPS/app checks and
compatible code rollback have not been exercised. No GCP resources, snapshots,
IAM, production state or live services were touched. No browser check applies to
this infrastructure-only change.

Validation: `./sigma test` passed all offline scenarios, Ruff, format, Pyright
(0 diagnostics), frontend typecheck and build. The focused monitor suite passed
8 cases during that full run and passed 9 cases in the final focused rerun;
shell syntax and `git diff --check` passed. `systemd-analyze` is unavailable on
this macOS host, so unit verification is pending on Ubuntu/GCE. Starlette/httpx
deprecation warnings are pre-existing. Actual hosted acceptance must still
verify monitor installation, READY retention, reboot recovery, auth/workspace/
artifact/accounting continuity, rollback compatibility and approved alert
routing. Coordinator handoff and dependencies are in the linked T136 message
file and PR.

## T135 backup and restore preparation (2026-10-25)

On branch `gray/t135-cloud-backup-restore` based on `origin/main` at
`ffb008f`, implemented an application-consistent daily GCE state-disk snapshot
service and persistent UTC timer. The service stops `sigma.service`, confirms
no SIGMA Compose containers remain, verifies the mounted filesystem resolves
to the configured GCE block device, syncs the mounted disk, waits for a new
snapshot to become `READY`, and only then applies retention (minimum 14 ready
recovery points). It writes success/failure markers, leaves failures visible
through systemd/journald, and restarts the app if it was active before the job.
`./sigma test` now runs eight offline backup/restore tests.

The read-only restore checker validates integrity and required tables for auth,
workspace-mapping and accounting SQLite files; saved identity/workspace mapping;
private SQLite/workspace ownership and modes; one-to-one workspace directories;
project JSON; artifact presence; and saved
paper TeX/PDF size and SHA-256. It checks ledger workspace references and
foreign keys, and reports reserved/unknown calls without rewriting state.
Exact host setup, backup, separate-disk restore, verification and troubleshooting
steps are in [Operations Runbook](OPERATION_RUNBOOK.md#5-daily-state-disk-backup).

Validation passed: `uv run python tests/state_backup.py` (8 tests), shell
syntax for both backup scripts, Python compilation, Ruff check/format, Pyright
(0 diagnostics), frontend typecheck/build, `git diff --check`, and
`env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` (all steps passed).
This macOS checkout does not include `systemd-analyze`; unit validation on
Ubuntu remains pending. No GCP command, resource, IAM change, snapshot, live
restore, or production data was touched. No browser UI changed, so no browser
check was applicable.

Hosted acceptance remains blocked on T127/T129 disk and service availability,
owner-approved least-privilege snapshot IAM, proof that app containers cannot
access the snapshot-capable GCE identity through metadata, and a separate
isolated recovery host/disk. Snapshot scheduling and successful creation alone
do not establish recoverability. Preparation took approximately 30 minutes;
commit and PR details are recorded in the handoff.
Review PR: [#142](https://github.com/bkramerext/sigma/pull/142); implementation
commit at handoff: `ac1a59422ecf104791cd77f8b2ad0cabc2750412`.

## T98 Red cloud-deployment checkpoint (2026-10-25)

On current `main` (`f76d834`), the existing host-readiness package, sponsored
cloud inference, and Python/Sage/TeX runtime passed the full offline `./sigma
test` suite. A local Colima persistent-volume smoke retained hosted-mode auth
state across backend restart and container recreation. Docker Compose v2 is
missing in this workstation, so the packaged Compose/Chrome check did not run;
the read-only production preflight correctly blocks on this macOS ARM64 host.

The live hostname resolves to `50.47.237.240`, but HTTP returned 406 and HTTPS
port 443 refused the connection; no SIGMA page or TLS endpoint was verified. No
GCP resources, DNS writes, OAuth changes, secrets, or paid provider calls were
made. GCE project/operator access and spend approval, production OAuth and
Secret Manager values, DuckDNS update access, a second Google test account,
rootless Ubuntu 24.04 host verification, and an approved backup mechanism
remain required. Full results and exact owner actions: [T98 cloud checkpoint](../messages/t98_red_cloud_checkpoint_20261025.txt).

## Current owner follow-ups (2026-10-25)

- LaTeX dialog launch simplification from `tickets/t95-t125-latex-dialog-ux-spec.md`
  (owner revision `cf47e1c`): removed the expanded-authoring toggle, pipeline
  bounds, checkpoint counters and ordinary restart control. The server chooses
  one-shot or long-form authoring automatically; compatible saved work still
  resumes when the user explicitly generates. A concise Start over action is
  available only when changed evidence/settings make existing work unusable;
  its consequence and possible provider usage are stated beside it. Generation
  now uses one primary action and plain activity/success/failure messages. An
  interrupted or failed dispatched request warns that provider completion or
  usage may be unknown and is never automatically retried. Saved versions and
  their TeX/PDF actions are unchanged.
- `tests/papers.py` passed, including the API disconnect cancellation/no
  publication regression. Real Chrome `browser_checks/t45_long_paper.py` and
  `browser_checks/saved_paper_library.py` passed with deterministic local
  fixtures at desktop/mobile widths. They verified automatic long-form
  selection, no silent retry after a simulated failure, simple activity and
  success feedback, saved versions and PDF access, plus the existing saved-row
  layout, yellow Remove action, left-aligned downloads, TeX/PDF downloads, and
  confirmed deletion. Frontend
  production build passed. The full `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL
  ./sigma test` passed all steps. No live or paid provider calls were made.
- Project header: About matches Home's compact style in normal and hover states.
  The desktop 3×2 pills are grouped by column: Difficulty/About,
  Model/Thinking, and Google/ChatGPT. The group now sits closer to the upper
  right with half-sized grid gaps; real Chrome confirmed the position and
  grouping. Narrow layout stays responsive.
- Real-Chrome checks now cover direct long-form start without a browser prompt,
  failure then retry, cancel, saved version/PDF, mobile dialog scrolling, and
  About placement/style. `browser_checks/t45_long_paper.py` and
  `browser_checks/header.py` passed in real Chrome; the full
  `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed, including Ruff,
  Ruff format, Pyright (0 diagnostics), frontend typecheck and production build.
  All checks used local deterministic fixtures; no paid provider calls or cloud
  changes.
- After syncing current `main` (`19e5bd7`), `./sigma test` passed all steps,
  including the frontend production build. Real Chrome
  `browser_checks/saved_paper_library.py` and `browser_checks/t45_long_paper.py`
  passed against deterministic local fixtures. The recents test now tolerates
  project initialization creating its research-session directory. The long
  paper browser fixture uses a unique project title so repeated runs do not
  collide with prior local fixture data.

Screenshots: `docs/evaluations/t45-paper-dialog/` and
`docs/evaluations/project-about-pill/`.

PR #108 merge-readiness refresh: fetched `main` at `f5388d8` (including Blue
#116, Gray #120 and subsequent main history) and merged it without conflicts.
The current-state summary and newer research/sample records in this file were
preserved. Real Chrome `browser_checks/t45_long_paper.py` and
`browser_checks/header.py` passed against the reconciled tree. The required
`env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed, including Ruff,
format, Pyright (0 diagnostics), frontend typecheck and production build. No
paid provider calls or cloud changes.
## Current state for newcomers (2026-10-25)

SIGMA is a local research workspace that stores questions, role responses,
computations and reports. Current tests establish specific engineering
behaviors on deterministic fixtures; they do **not** establish that SIGMA
reliably discovers correct research results or outperforms a single researcher.
Investigator and Skeptic use the same underlying model, so their agreement is
structured scrutiny, not independent verification.

**Research-quality evidence:** one earlier live Maximum Regions run used a
solution-bearing stock strategy and cannot count as independent discovery. A
later answer-free live run produced a reviewed proof candidate, but exact role
inputs were not retained and output fields were truncated; its independence is
unverified. T146 later completed one authorized same-model paired case on a
single scheduling task. Both arms found the optimum; the Skeptic added no
substantive correction and the single-role baseline later withdrew its correct
conclusion after an invalid critique. This remains a descriptive
within-session observation; it does not test cumulative cross-strategy or
cross-session value. The unfamiliar-task cumulative comparison remains
**not frozen and not run**. Its current design is [T114 cumulative
preregistration](evaluations/T114_CUMULATIVE_PREREGISTRATION.md); the old
within-session protocol remains [historical](evaluations/T114_MATCHED_BUDGET_PREREGISTRATION.md).
No further live run is authorized by T114.

**What is established:** the dated entries below link to actual tests, exports,
browser observations and bounded engineering results, with their stated limits.
Computations establish only their recorded finite scope. No model consensus,
saved label or polished report alone establishes a theorem. See [Getting
Started](GETTING_STARTED.md), [research evaluation records](evaluations/), and
the [researcher-centered product limits](RESEARCHER_CENTERED_SIGMA.md).

**Still unverified / launch blockers:** unscripted multi-agent advantage,
general research quality, and independent proof correctness remain unverified.
The proposed blind study still needs independent task/key review and
contamination/provenance assessment, sealed-key custody, proven model-visible
isolation, shared output-boundary validation, independent graders, current
pricing and enforceable budget controls, and explicit owner approval. Cloud deployment also
has host-specific acceptance requirements; those are recorded in the Red/cloud
entries below and are not implied by local checks.

The entries that follow are the retained chronological engineering and
evaluation history; newer summaries do not replace or rewrite them.

## Round 2 Increment 18 — hosted research and export integration (2026-10-25)

Extended the deterministic authenticated hosted-session API scenario to follow a
completed sponsored research session through the owner-facing project export,
saved Outcome verification label, text report download, and a fresh FastAPI
process reading the same project, session, Outcome, and report from the durable
workspace. The fixture uses the production API and workspace boundaries with a
test-only verified-principal adapter and fake OpenAI Responses transport. It
does not contact Google OAuth or OpenAI. Code inspection plus this joined check
found no Blue-owned session-engine defect requiring behavioral changes; the
gap was that existing hosted inference coverage ended before the user's export
and restart workflow.

**Acceptance state:** simulated authenticated research → saved Outcome → export
→ new-process recovery: PASS. Workspace ownership, sponsor-only inference,
budget admission/holds, idempotency and failure cases remain covered by the
same existing scenario. The full suite passed, including this extension,
Ruff, format, Pyright, frontend typecheck and production build. No real provider
calls, cloud resources, or production secrets were used.

The packaged Compose/Chrome acceptance did not run. The repository script first
stopped because this host lacks the `docker compose` CLI plugin; routing it to
the installed Compose v2 binary then stopped before app startup because the
ARM64 Docker engine lacks Buildx and produced ARM64 images where the package
requires amd64. Thus no new real-browser hosted acceptance is claimed. Real
Google OIDC, a hosted browser session, GCE rootless execution and the Red-owned
#98/#99 deployment gates remain **UNVERIFIED**; Red owns those host checks, and
actual hosted provider usage remains unauthorized. Increment 18 remains
partially verified pending coordinator disposition of these dependencies.

The actual synthetic hosted project and text-report response bytes produced by
the accepted API workflow are retained in
[`increment_18/exports`](evaluations/increment_18/exports/manifest.json). The
manifest records project/session IDs, capture/app commit `adb3205`, initial
artifact publishing commit `ab35f2f`, exercised actions and omissions. These
are exports of the deterministic fixture session, not live research or hosted
customer data.

Elapsed worker time was approximately 40 minutes through PR-ready handoff.
The focused change is on `blue/increment-18-hosted-research`; see
[`messages/i18_blue_r4r.md`](../messages/i18_blue_r4r.md) for exact commands,
scope and outstanding acceptance.

## Issue 117 — Release safety and test reliability (2026-10-25)

Fixed the Ubuntu host-installer test hazard by extracting the non-mutative
Ubuntu 24.04 identity guard into `deploy/gce_host_guard.sh`. Regression tests
exercise quoted and unquoted Ubuntu IDs, Debian and Fedora, and statically
verify the installer guard precedes package and filesystem operations. No test
invokes the installer. The separate preflight exit-code report was traced to
the test asserting `BLOCKED`/2 on a matching Ubuntu host with failed service
checks; a controlled Ubuntu fixture confirms those results correctly report
`FAIL`/1, while a Debian fixture reports `BLOCKED`/2.

The recurring mocked `stop_servers` failure reproduced with the shell's
exported `SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL` and passed when it was unset. The
UI lifecycle test now clears that value and the paired OAuth settings in its
test context. `sigma test` now runs all approved offline checks after ordinary
failures, prints a complete failed-step summary, returns nonzero, skips the
offline artifact writer and frontend build after an earlier failure, and
rejects commands outside the known check set. `setup` remains fail-fast.

Expanded Ruff lint to `deploy/`, `browser_checks/`, `scripts/`, and
`docs/evaluations/`; it found and fixed import ordering, an unused import, a
credential-prefix check, a keyword-built dictionary, and non-executable
shebangs (13 findings in the audited paths). Format checks now include
deployment and support scripts: 105 files passed at the initial audit. After
syncing current main, the gate also covers the new Increment 17 audit script
and current-main readiness script; 107 files now pass. The audit found 20
files that
Ruff would reformat across the broader support paths; the six offline
evaluation/support scripts are formatted, while 13 legacy browser checks and
one evaluation exporter remain lint-gated without bulk formatting churn. CI is
pinned to Ubuntu 24.04 and runs host-safety and environment isolation checks
before the full suite.

After the initial branch was created, main advanced through PR #122 to
`cf7dcb024996b95a0913c75438c6d17c4c065299`, then through PR #112 to
`f5388d8`, and through PRs #123/#126 to `f73a749`. All four updates were merged into the T117 branch, preserving Green's
frontend changes. The PR #122 deterministic CLI-level BLOCKED test remains
alongside the Ubuntu FAIL/1 fixture. CI run #431 exposed that the newly merged
Increment 17 audit script had an invalid shebang for its non-executable mode
and needed Ruff formatting. Removed the stale shebang and formatted that file;
its direct offline invocation reported the expected quality-gate result and
zero new paid calls. CI also caught an executable bit on current-main
`scripts/increment15_readiness.py` without a shebang. Removed that bit because
the workflow invokes it with Python. Both were narrow quality-gate fixes with
no logic changes. The synchronized branch full local suite passed, including
Ruff over 107 files, Pyright, frontend typecheck and production build. Ubuntu Actions run #443 passed on final code head `48be67f`, including the
focused safety/lifecycle checks and full repository verification. Elapsed time
through final CI completion was approximately 45 minutes. Actual Ubuntu package
installation, systemd setup, rootless Docker, and installer execution remain
unverified and were not attempted.

Validation passed: `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` (all
scenarios, expanded Ruff lint, Ruff format, Pyright, frontend typecheck and
production build); `tests/gce_host.py` (10 tests); `tests/tooling.py` with and
without the inherited bootstrap variable; and `git diff --check`. The full
suite's 24 synthetic Increment 15 records had zero model calls/cost. No
provider calls, GCP resources, installer execution, or real-browser checks
occurred. T117 changed no product UI; Green's main-branch UI changes remain
present. The merge sync also took current main versions of two overlapping
protocol scripts; those are outside the T117 diff and stay separate from the
postponed stock-session implementation. Ubuntu host/systemd/rootless-Docker
behavior remains limited to safe fixtures; Ubuntu CI validates regressions without running the installer or
requiring root.

Final T117 integration (2026-10-25): fetched main at `6686e6f`, which includes
coordinator PR #132 (`a366038`) and subsequent main PR #130. Both fixture lint
corrections are present from main: import ordering in
`browser_checks/t47_conclusion.py` and the merged sample/recent route condition
in `browser_checks/project_create_contract.py`; neither was reimplemented in
T117. The current-main merge is commit `f5b5a61`. After the merge,
`env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed, including Ruff
lint/format across 107 files, Pyright, frontend typecheck/build, and all
scenarios. Direct `tests/gce_host.py` passed 10 tests; `tests/tooling.py`
passed with a synthetic inherited bootstrap value and with it unset. No
installer or infrastructure work was run. Ubuntu Actions run #461 passed on
code head `5efdf3f` with focused host/lifecycle checks and full verification.

## Issue 114 first increment (2026-10-25)

Audited the Increment 6/14 blind plans and Increment 15 offline preparation,
the answer-bearing stock-sample Maximum Regions trial, and the later answer-free
live trial. No matched-budget blind result exists. The later live run's
mathematical candidate and Skeptic revision remain a single live observation;
missing exact request bodies and historical response-field truncation prevent
its use as verified independent-discovery evidence. Deterministic archived
sessions and fixtures remain separate from live trials.

Added a proposed paired protocol and USD $48 / 96-call hard-ceiling sheet in
[the issue 114 evaluation record](evaluations/T114_MATCHED_BUDGET_PREREGISTRATION.md)
([PR #116](https://github.com/bkramerext/sigma/pull/116)).
The existing offline manifest and audit now check per-call and aggregate input
and output token budgets. Twenty-four synthetic records passed the dry-run;
the readiness report still blocks live work for absent isolation, model,
graders and owner authorization. This is setup evidence, not research-quality
evidence. No provider calls, paid inference or cloud work occurred.

Validation: focused Increment 14 protocol/audit and Increment 15 pair dry-run
passed. `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed all
scenarios, Ruff, format, Pyright, frontend typecheck and production build after
locked frontend dependencies were installed. The first full-suite attempt
stopped at format; after formatting, another stopped because `tsc` was not yet
installed. After rebasing onto main `8562c89`, one full run transiently failed
at the copied-workspace assertion in `tests/storage.py`; that scenario passed
alone and the subsequent full run passed all scenarios, Ruff, format, Pyright,
frontend typecheck and production build. Actual elapsed time for the first
increment: approximately 35 minutes. No browser surface changed. Matched live
comparison, independent task/key review, runner isolation, pricing verification,
blinded graders and owner authorization remain outstanding.

## T89 ship-ready stock sample curation, increment 1 (2026-10-25)

Started from fresh `gray/t89-stock-sample-curation` at current `main`
`8562c89` after PR #115 merged, then merged `main` `950c810` into the branch
without rewriting history; the `docs/STATUS.md` conflict was resolved with
both this record and the new T114/main status preserved. Reframed the opening of all 17 sample briefs
in conversational language while retaining their research questions, evidence
requirements, and exit criteria. Added 12 bounded, human-authored starting
strategies across seven samples: Algorithm Design, Constrained Binary Strings,
Operation Narrow Passage, RH, Scientific Investigation, and both Warp Drive
samples. Set Nonconsecutive Subset Sums, Operation Narrow Passage, and Warp
Drive Engineering to Hard. Kept Jesus/cannabis difficulty unset for editorial
review; Arrival remains in the current `Other` domain pending taxonomy review.

Removed a direct answer spoiler from the active Maximum Regions starting path.
Its full previous proof, strategy identity, and provider provenance remain
unchanged in removed-strategy history; the active starter now guides the reader
to find an upper bound and an attaining arrangement. No project IDs, session
evidence, outcomes, original research text, or provenance were changed. The
previous Maximum Regions strategy was archived rather than discarded. The five
Subset Sums sessions remain deterministic fixtures, not provider research. No
inference calls were made, and the proposed Maximum Regions → Operation Narrow
Passage → RH authentic-session order is awaiting a separately approved spend
cap. The cost model and provenance plan are in
`evaluations/t89-stock-sample-curation-increment1.md`.

**Acceptance matrix: PASS 8, FAIL 1, BLOCKED 1.** Editorial implementation,
strategy guidance, metadata review, newcomer path, no-spend session proposal,
identity/history preservation, ownership boundaries, and focused checks pass.
The full-suite tooling assertion is FAIL; authentic stock sessions are blocked
on a separate budget approval, and none were fabricated.

Focused checks passed: `tests/recents.py` (17 samples, metadata, independent
copying, archived Maximum Regions proof and non-spoiling starter),
`tests/test_sample_copies.py` (9 tests), `tests/make_sample.py` (export/import
with a real v5 legacy fixture), `tests/example_math.py`, and
`tests/agentic.py`. Real Chrome `browser_checks/recents.py` passed against a
fresh isolated UI and provider fixture (Samples/Recent, direct copy, strategy
rendering, save, and source immutability). Ruff check/format, Pyright, frontend
typecheck/build, and `git diff --check` passed.

`./sigma test` ran and stopped at the known, unchanged
`tests/tooling.py:177` mock expectation that `stop_servers` be called once; it
was called zero times. Every later suite command was run individually under
isolated temporary state and passed, including cloud/workspace/storage,
deployment/host, UI registry, type checks, and production build. Therefore the
full-suite result is **FAIL (existing tooling assertion)**, not a pass. No
provider calls, live OAuth, or GCP resources were used. The active-branch
acceptance detail and test evidence are in
`evaluations/t89-stock-sample-curation-increment1.md`. Elapsed time from fresh
branch creation through final PR-ready push: approximately 22 minutes
(09:41–10:03 PDT, 2026-10-25).

## T89 stock sample catalog audit (2026-10-25)

Gray started from current `main` `7a2f445` and inventoried all 17 shipped
samples against their canonical project records, saved evidence and PR #74's
17-sample Chrome study. The audit records current domain/difficulty, problem,
strategies, stock sessions/outcomes, educational purpose, and a KEEP/REVISE/
CONSOLIDATE proposal with before/after rationale. Sixteen samples have no
saved stock session; Nonconsecutive Subset Sums has five deterministic fixture
sessions, all mixed with unresolved general proof obligations. PR #74's
historical Maximum Regions provider export is kept distinct from stock sample
history. No sample was removed, consolidated, or substantively rewritten; RH
remains the flagship. Owner decisions are listed in
`evaluations/t89-stock-sample-catalog.md`.

The only data correction is `counting-constrained-binary-strings`: migrated its
sample document from schema 6 to supported schema 8 and set its clearly
elementary recurrence exercise to Easy. `tests/recents.py` now pins the
17-entry catalog count and verifies that metadata through catalog loading and
an independent copied project. Focused recents, copy-independence (9 tests),
sample-export, and deterministic math checks passed.

`./sigma test` reached `tests/tooling.py` and failed at its existing mocked
`stop_servers` assertion. The same focused failure reproduces unchanged on
`origin/main` `7a2f445` in a detached worktree. Every command after that point
in the suite was run individually and passed, including cloud/storage checks,
Ruff check/format, Pyright, frontend typecheck and production build. Thus the
full suite is **not reported as passing**; this known baseline failure is
outside the T89 diff. No real provider calls were made. The browser coverage
is PR #74's reported study, not a new T89 Chrome run.

## AI paper dialog polish (2026-10-25)

Reduced unused space in the TeX dialog, increased its explanatory text to 14px,
and made the dialog height follow its contents while capping the completed
preview to a viewport-height scroll area. The header action now reads
“Cancel”. During generation, the duplicate disabled “Authoring…” button is
gone; Generate becomes a “Cancel generation” button in the same controls row,
and the status line no longer carries a duplicate cancel action. Long-form
generation now starts directly from Generate without the white browser-native
confirmation; the static bounds remain visible before start and checkpoint
restart keeps its explicit confirmation. A forced temporary generation failure
in the Chrome check confirms the error remains visible and Generate is
re-enabled for retry.
Added the Project Export checkbox label exactly as “Open in browser tab”. When
checked, the saved-PDF link opens a browser tab and requests inline PDF
disposition; when unchecked, the link downloads as before. The PDF endpoint
keeps attachment as its default, so existing downloads are unchanged.

Updated `browser_checks/t45_long_paper.py` to exercise the no-prompt start,
failure recovery, progress cancel, desktop and 390px mobile scrolling, completed-preview scrolling, inline PDF
opening and attachment fallback, initial dialog focus, and focus restoration.
Real Chrome passed. Captures are in
`docs/evaluations/t45-paper-dialog/`: owner-provided desktop before, completed
desktop and scrollable mobile after, retry-ready error, and authoring progress.
The browser regression verifies the version count increases after retry, so an
older saved paper cannot mask a failed generation. `env -u
SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed, including Ruff,
formatting, Pyright, frontend typecheck, and production build. No paid provider
calls or cloud changes. After merging the latest `main` update, reran
`env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` and the focused real
Chrome `browser_checks/t45_long_paper.py`; both passed on the published tree.
The latest follow-up additionally verifies direct start without the browser
confirmation, retry after a simulated service failure, in-place cancellation,
and a newly saved version.

## Adversarial review transparency and documentation cleanup (2026-10-25)

The README and Product Rationale now state that Investigator and Skeptic use
the same underlying language model. They describe their challenge-and-objection
process as structured scrutiny rather than independent validation, note their
potential shared biases, and describe different-model review only as a possible
future enhancement with no release commitment.

Moved `JOURNAL.md` to `docs/JOURNAL.md` with `git mv`; its blob hash is unchanged
and all 285 lines remain intact. The README, contributor guidance, and software
factory documentation now point to the new location. Repository search found
no stale root-path references, and the new local links resolve. `WOLF_TODO.md`
remains because it still documents substantive, uncompleted evidence and
writing requirements that the concise essay does not cover; deleting it would
discard those open items. The essay was left unchanged.

`env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed, including Ruff,
Pyright, frontend typecheck, and production build. No paid provider calls or
cloud changes.
## AI paper disclosure and preflight explanation (2026-10-25)

The TeX authoring dialog now explains that SIGMA uses the complete recorded
research history, distinguishes findings from conjectures, identifies gaps, and
produces an AI-generated paper that has not been independently verified. Model,
usage, and generation bounds remain visible. The deterministic TeX assembler
adds an attribution beneath the title and author, followed by an “About this
paper” section before the introduction. These additions are independent of the
authoring prompt and therefore travel with the saved TeX and compiled PDF;
existing evidence references, warnings, and obligations remain assembled as
before.

Focused regression coverage checks the disclosure text and ordering in the
assembled and archived TeX, plus the dialog language and retained model/bounds
in real Chrome. `uv run python tests/papers.py`, the real-Chrome
`browser_checks/t45_long_paper.py`, and `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL
./sigma test` passed. The first full-suite attempt caught only Ruff formatting
in the new assertions; after formatting, the complete suite passed, including
frontend typecheck and production build. No paid provider calls or cloud
changes.

## Home and text-copy polish follow-up (2026-10-25)

Home Projects now starts at matching top and left offsets, with each edge half
the previous desktop margin. Narrow mobile keeps the Projects list below the
wrapping account pills while matching its top and left margins. New Project
remembers the complete last successfully created form values in browser-local
storage; failed attempts do not replace them. Project description and strategy
approach rows have adjacent copy controls. They copy plain text in either
display mode, and show a temporary checkmark that remains clickable for another
copy. The artwork credit is split as “Brian Kramer &” / “OpenAI Models” and
rendered in uppercase to match the SIGMA artwork's title lettering.

Real Chrome checks cover the exact artwork credit lines, desktop/mobile Home placement, create success and
reopen persistence, copy repetition for both text areas, and Markdown-to-plain
clipboard output. `browser_checks/project_create_contract.py` and
`browser_checks/t47_conclusion.py` passed. Screenshots:
`/tmp/sigma-home-projects-desktop.png`, `/tmp/sigma-home-projects-mobile.png`,
`/tmp/sigma-copy-buttons-desktop.png`, and
`/tmp/sigma-copy-buttons-mobile.png`. `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL
./sigma test`, frontend typecheck/build, and `git diff --check` passed. No paid
provider calls or cloud changes.
## T93 mathematical formatting showcase and project creation regression (2026-10-25)

Rebased the T93 work on current `main` (`f3bae10`, including the README update).
The About Key Features section, README capabilities list, and `WOLF.md` essay
now describe AI reformatting of plain-text project descriptions and saved
Conclusions into Markdown with typeset equations. They say the saved text stays
available and the formatted mathematics still needs review; this is not claimed
as mathematical verification.

Brian's New Project screenshot exposed that shared settings state sent the
edit-only `show_advanced_outcome_details` preference to the strict create API.
Project creation now sends only the create contract fields. A real-Chrome
regression asserts the submitted request omits that preference and retains the
API's strict error response without creating test data. A second Chrome check
asserts the About copy and layout at 1440, 390 and 320 px. Both focused checks
passed; screenshots are `/tmp/sigma-about-math-1440.png`,
`/tmp/sigma-about-math-390.png`, and `/tmp/sigma-about-math-320.png`. The full
`env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed after the frontend
change, including typecheck and production build. No provider calls or cloud
changes. The broader legacy `browser_checks/settings.py` did not reach its
creation assertions in this local cloud-auth environment because its initial
“Checking AI…” expectation was not met; the standalone request-contract check
covers the reported regression directly.

The Conclusion formatting controls now show the same visible “Formatting with
AI…” label beside the hourglass in project descriptions, strategy approaches,
and saved Conclusions, with consistent 6px spacing. The simple Outcome view now
offers a quiet, underlined “Advanced Outcome” action below the summary; it saves
the project preference and opens the full findings. The redundant excerpt note
was removed. Focused real-Chrome checks cover all three formatting controls,
the persisted preference link, rendered/raw modes, and desktop and narrow mobile
layouts. Screenshots are `/tmp/sigma-project-markdown-formatting.png`,
`/tmp/sigma-project-markdown-formatting-mobile.png`, and
`/tmp/sigma-strategy-markdown-formatting.png`. `t47_conclusion.py` passed, and
`env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed in full,
including frontend typecheck and production build. No provider calls or cloud
changes.
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
The API conversion request also accepts a bounded optional session ID for saved Conclusions. Sponsored-cloud provider attempt accounting remains active for both project and Conclusion conversions; `tests/text_views.py` and `tests/cloud_research_api.py` cover the API route and usage accounting. The rebased tree passed `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` and the focused real-Chrome paper dialog check.

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

The project header uses a compact About pill that matches Home's color, type,
border and dimensions. Desktop controls form three columns and two rows:
Difficulty/Model/Thinking, then About/Google/ChatGPT. On narrow screens About
remains directly below Difficulty in the responsive two-column arrangement.
The Home header orders its About/Admin group left of Google/ChatGPT and keeps
the intended gaps between pills.
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

## Increment 22 / issue #146 — offline preparation (2026-10-25)

Read the complete issue #146 and started from fresh `main` (`19e5bd7`) on
`blue/increment-22-issue-146`. The preparation record is
[`increment_22/preparation.md`](evaluations/increment_22/preparation.md).
It proposes one custom finite scheduling problem and a strong four-call
self-critique baseline against the actual two-cycle, four-call SIGMA session.
No stock task is reused. This remains an exploratory single-case comparison,
not a longitudinal or general-superiority claim.

The authored seven-job/two-machine task and independent exhaustive checker are
preserved with hashes in [`increment_22/evidence/offline-manifest.json`](evaluations/increment_22/evidence/offline-manifest.json).
The checker validates the proposed 13-unit schedule and enumerates 2,016
machine assignments/orders, finding an exact 10-unit minimum; M1-only jobs
also provide a direct matching lower bound. This is a validated offline oracle,
not provider research evidence, and its answer is withheld from model contexts.

Proposed run: OpenAI API-key billing, `gpt-6.1-sol`, high reasoning, standard
tier, no tools/search/retries/fallback; four calls per arm, 4,096 output tokens
per call, 200,000 reserved input and 16,384 output tokens per arm, 15 minutes
per arm / 45 minutes overall, $0.67 local pre-dispatch cost ceiling per arm.
The conservative price-based reservation is $0.66384 per arm / $1.32768 total;
operator verification that the selected OpenAI API project has a $1.40
monthly limit with **Enforce a hard limit** enabled remains required.
The 1,024-token cap included hidden reasoning and was not adequate to defend
against clipping at high reasoning. The smallest recommended adjustment is
4,096 output tokens/call. Clipping remains an incomplete result, is not scored
as incorrect, and is not retried. The output limit includes visible and
reasoning tokens; see the official [Responses API reference](https://developers.openai.com/api/reference/resources/responses/methods/create)
and [reasoning guide](https://developers.openai.com/api/docs/guides/reasoning).
The complete request, limits, cost derivation, execution procedure and
authorization wording are frozen in `evaluations/increment_22/` and hashed in
`increment_22/evidence/frozen-manifest.sha256`.

Reconciled with current `main` (`803a62d`) in merge commit `2eb1ae0`; Green
T95/T125 and Cloud T129/T130/T131/T133 changes are retained. The latest full
`./sigma test` passed: backend scenarios, Ruff, formatting, Pyright (0
errors), frontend typecheck and production build. The independent checker
validated its exact 10-unit optimum across 2,016 assignment/order cases; all
11 offline cumulative-budget tests passed. The real-Chrome Home running-status
check passed against a fresh local fixture. One initial browser attempt used
an already-populated project root and failed its fresh-fixture assumption; the
isolated rerun passed. After later `main` updates, the latest full `./sigma test`
passed again, as did checker execution, frozen-manifest verification, and all 11
offline budget tests. The final post-merge Actions run is pending push. No provider calls or spending occurred. The trial is not authorized,
and no Increment 23 work or Cloud deployment operation was started.

## Issue 118 — harden within-session blind comparison (2026-10-25)

Revised the T114 proposal after adversarial review. The active design uses three
repeats for each of six tasks and two evidence variants (36 paired comparisons,
72 arm runs), but treats only the six tasks as independent clusters. It reports
all task-level effects and a six-cluster interval and does not claim confirmatory
power. It tests within-session adversarial review versus single-role self-review;
it does not test cumulative persistence (separate issue #119).

Added a common six-field output normalizer, identical character caps, explicit
clipping and native schema-truncation audit fields, scorer-only anonymous
packets, output-digest validation and a task-cluster summary. Removed
objection-uptake scoring and replaced the old decisive `+0.40` threshold with
task-outcome/reasoning primary scoring and exploratory interpretation. The
proposal now requires an independent curator to document task/key/model-family
provenance and contamination, separate key custody, and graders independent of
the task author, curator, implementer and provider run. A one-pair throwaway
shakedown is specified but remains **not authorized**.

Focused protocol and audit regressions passed. The offline paired harness
validated 72 synthetic records across 36 pairs with zero model calls or cost.
The changed Python scripts passed focused Ruff checks and `git diff --check`.
`./sigma test` stopped at the existing `tests/tooling.py::check_ui` mocked
`stop_servers` assertion (expected one call, got zero); the runner stopped
before Ruff/format, Pyright, frontend checks and production build. No browser
workflow changed. No paid inference, live shakedown, cloud operation or browser
check occurred. No project was modified or exercised, so no project export was
created. The newcomer summary above is retained; the concurrent Green
PR #108 also edits `STATUS.md`, so integration must preserve that summary and
this issue record.

## Round 2 Increment 19 — readable Outcomes and actionable pauses (2026-10-25)

Reviewed current `main`, Green PR #97, and merged PR #108 before editing. The
KaTeX renderer and explicit AI text-conversion path were already present on
`main`; PR #97 remains open against an older base. Increment 19 extends the
existing renderer for conservative bare math tokens in historical mixed prose,
translating recognized Greek letters, operators, compact powers/subscripts, and
simple slash fractions into KaTeX syntax only in the display projection. Code,
links, HTML, and long underscore identifiers are left as authored prose. It
does not rewrite saved conclusions. Simple and
Advanced Outcome start typeset when a conclusion contains recognizable math;
the original source remains available by toggle. Explicit AI formatting remains
available for less regular notation and displays its warnings plus a clear
statement that formatting is not verification.

Research session projection now gives a concise safe next step for manual pause,
failure, an interrupted dispatched call, restart without a recorded in-flight
request, project/account/model guards, context/storage limits, cost limits, and
ended call/duration limits. The notice sits above the Outcome narrative in both
reader modes. Ambiguous provider calls require a usage/billing check; a resumed
session does not replay an interrupted attempt. Existing computation provenance
stays above the agent-authored Conclusion.

Real Chrome on the archived RH-style session verified legible KaTeX in both
default Simple and Advanced views, exact saved-source access, the copper control,
paused cause/next action and Resume visibility, evidence ordering, and mobile
layout. The full `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` suite,
frontend typecheck/build, Ruff, Pyright, and `git diff --check` passed. No live
provider request or resume action occurred. The browser used an in-memory view
fixture; the only preserved project export is the byte-identical historical
T17.8 SIGMA export, with fixture changes explicitly excluded in its manifest.

Mathematical display is a reading aid, not a proof or verification. The
normalizer is intentionally token-based and conservative; unusual notation can
still use the existing explicit AI formatting path or the exact saved-source
view. PR #97 and issues #93/#95 remain open pending coordinator review and
acceptance; this entry does not close them.

## Round 2 Increment 20 — newcomer and sample credibility review (2026-10-25)

Blue reviewed the newcomer surfaces and the curated 17-sample catalog against
the T89 audit, preserving research scope and avoiding overlap with Green's open
T95 UI branch. The canonical sample IDs remain intact and RH remains the
flagship.
The sample review found no content basis for unilateral removal, consolidation,
or substantial rewriting. It added the omitted primary 2022 RDB7 dataset citation
to the catalysis sample without changing its problem or scope. The review
records a per-sample credibility assessment, cross-surface wording gaps, owner
decisions, verification, and limitations in
[the Increment 20 review](evaluations/increment_20/domain-credibility-review.md).

Real Chrome opened the existing Nonconsecutive Subset Sums sample as an
independent copy and inspected all five mixed/unresolved saved fixture sessions,
their evidence and report, plus desktop and mobile layouts. The Current
Understanding and historical-session summary visibly mark the records as
deterministic fixtures. A separate human proof note remains outside this sample
history and is not presented as a SIGMA result. The exact project export and
capture manifest are retained in
[Increment 20 exports](evaluations/increment_20/exports/manifest.json). No new
session, provider inference, or cloud operation occurred. `./sigma test` passed
after locked frontend dependencies were installed, including lint, format,
Pyright, typecheck, and production build. The established `about.py` browser
check still expects the obsolete accessible label “About SIGMA”; a direct Chrome
check using the current “About” label exposed the expanded copy's “Different
minds” wording and absolute recoverability promise.

Increment 20 first-user acceptance remains **open**: Getting Started does not
define Project, Session, and Outcome clearly or disclose that both research
roles use the same underlying model; About's “Different minds” wording conflicts
with the README; and sample cards omit the problem description already supplied
by the sample catalog API. PR #135 intentionally retains title plus
strategy/difficulty metadata on Samples, so the coordinator must decide after
that review whether its presentation satisfies newcomer selection. Gray/Green
own the About/documentation implementation. The proposed warp-drive
pathway/consolidation remains an owner decision; both sample identities remain
preserved pending that decision.

## Round 2 Increment 21 — matched-budget evaluation readiness audit (2026-10-25)

Audited the T114 Revision 2 design, merged T118 protocol implementation (PR
#123), six task packets, agent allowlist, normalizer, record auditor, offline
pair generator and readiness gate. The protocol remains proposed, unfrozen,
unexecuted and unauthorized; the task/answer set still needs independent
curation, the real SIGMA and strong single-role adapters are not tested, model
input isolation and independent grading are not established, and actual
matched settings/cost enforcement are not verified. The current SIGMA-to-common
artifact projection can omit citations, computation feedback, objections and
open obligations. The audit now requires schedule-position records matching
the randomized manifest, but cannot authenticate them against an actual runner.
These fairness and schedule issues require pre-freeze resolution. The existing design is
within-session only (`n=6` task clusters), not evidence about persistence or
superiority.

A zero-cost adversarial probe showed the generic auditor accepted a six-pair
manifest where the protocol requires 36. The version-3 default audit now checks
the full six-task × two-variant × three-repeat matrix, task/packet/protocol/
agent/audit/key/scoring hashes, assignment and declared schedule positions, and
fixed caps before accepting records. Its unit fixture opts into partial-
manifest mode explicitly; 23 synthetic manifest/record mutations
are rejected by the offline dry run. The remaining live gates are documented
in [the Increment 21 readiness audit](evaluations/increment_21/readiness-audit.md)
and reproducible machine outputs/hashes are retained in
[evidence](evaluations/increment_21/evidence/). Focused protocol/audit/dry-run,
readiness and retrospective checks passed. The full `./sigma test` passed after
installing locked frontend dependencies. No provider calls or cost occurred;
no comparative result is claimed.

## Round 2 Increment 22 — cumulative collaboration trial preparation (2026-10-25)

Prepared one custom, independently enumerable two-machine scheduling case for
issue #146. The exact checker finds the proposed 13-unit schedule feasible but
suboptimal; enumeration over 2,016 eligible machine/order cases finds a
10-unit optimum, also supported by the M1-only D/F/G lower bound. The complete
task, checker result, frozen baseline prompts, scoring rubric, caps and execution
procedure are retained in [Increment 22](evaluations/increment_22/).

Implemented a persisted, fail-closed pre-dispatch ledger shared by SIGMA and
the baseline dispatch adapter. It reserves serialized request bytes plus
8,192 input tokens, output ceiling and conservative cost before dispatch;
unknown or in-flight calls hold their full reservations and block further calls.
The real SIGMA request-path regression test inspects reserved request IDs/bytes
and settlement. Provider `max_output_tokens` clipping is retained as a partial
incomplete result with usage; it is not scored as incorrect and is not retried.
Ruff I001 and RUF007 in the checker were corrected. Offline checks only; no
provider inference or spend occurred. Following the API token-counting guidance,
the proposed output cap is now 4,096 per call: 1,024 could leave too little
visible room after high-effort reasoning. This is a reasoned adjustment, not a
live verification of no-clipping.

Brian's authorization for one trial is recorded in the latest PR #150
coordinator comment (2026-10-25 22:48 UTC), with the frozen model and strict
limits. Latest `main` (`bcda1de`) is integrated in merge commit `cc3d766`,
retaining its T131/T132 work and all Green/Cloud/evaluation artifacts. The
frozen manifest still verifies exactly; it was not rewritten. The full local
`./sigma test` and all 11 budget tests passed on this merge. No provider request
was made and no spend occurred: the execution gate fails closed because this
runtime and checkout `.env` have no OpenAI API key, and no OpenAI admin
credential or project/key metadata is available to independently verify the
key's project, current project usage, or model access. The owner's limit
confirmation does not establish those separate checks. Trial outputs and
actual trial elapsed time therefore do not exist. No Increment 23 work or
Cloud deployment operation was undertaken.

Final verification for this preparation SHA: `./sigma test` passed all lifecycle,
research, storage, API, Cloud-regression, Ruff, format, Pyright, frontend
typecheck, and production-build steps. `git diff --check` and the frozen SHA-256
manifest validation passed. The optional existing Chrome settings fixture check
did not initialize its expected API-key fixture state: the browser opened with
the stored “ChatGPT sign-in · Google sign-in required” state and failed its
initial `Checking AI…` assertion. No browser-triggered provider request was
made; this check result is retained as an environment/fixture mismatch, not a
product conclusion.

## T130 — Public DNS and HTTPS preparation (2026-10-25)

Based on `main` at `455d752`, added a read-only public endpoint validator in
`sigma.public_endpoint` and `deploy/verify_public_endpoint.py`. It verifies the
hostname resolves only to the owner-provided IPv4, TCP 8000/5173/2375/2376 are
unreachable, HTTP `/` redirects to canonical HTTPS, default TLS verification
succeeds, a SPA deep link returns 200, and `/api/cloud-auth/status` reports
ready hosted auth. Expanded Caddy routing to include exact `/api`, removed the
unused UDP 443 host publish, and documented the public firewall and external
probe procedure. No DNS, GCP firewall, or public endpoint was changed.

`./sigma test` passed all scenarios, Ruff check/format, Pyright (0 diagnostics),
frontend typecheck, and production build. Seven focused public endpoint tests
cover success and DNS, redirect, SPA, malformed/unready API, and direct-port
failure cases; existing deployment package and GCE host tests also passed.
`bash deploy/validate-local.sh` built both locked images but could not start its
disposable stack: the Colima Docker engine could not mount the worktree's
`/private/tmp/.../deploy/.local-secrets...` fixture path. The script exited
before browser exercise and cleaned up its temporary stack; no real-browser
or hosted HTTPS evidence was obtained. Rerun the packaged browser smoke from a
Docker-shared checkout path if available.

Public DNS/TLS acceptance remains pending the provisioned VM, Brian's
owner-authorized DuckDNS update and GCP ingress decision, and production launch
prerequisites. Do not treat offline or local checks as public acceptance.

PR155 review correction: public HTTP requests now use a no-redirect urllib
handler and return 3xx status plus `Location`; HTTPS requests still use an
explicit `HTTPSHandler` with `ssl.create_default_context()`. A loopback HTTP
server regression test proves the redirect destination is not requested.
Seven focused public endpoint tests and the full `./sigma test` passed after
this correction. No production host or DNS was contacted.

## Round 2 Increment 23 — T146 evidence-driven diagnosis (2026-10-26)

Started from current `main` at T146 merge `13a63c470e42d5d1fb478ba32641d291f117e2af` on `blue/increment-23-issue-147`. Read issue #147 and preserved T146 evidence before investigation. The Skeptic's `assessment=stop`, `stop_reason=unresolved`, and `strategy_contribution=solution` are internally inconsistent model fields. The coordinator independently validates the completed objective and, because the review is achieved with no open obligations or next question, records `stop_productive_conclusion`. The raw Skeptic output is preserved; the artifact separately records the coordinator decision, objective review, strategy review, evidence references, and unverified status. The prior-session continuation path filters by the achieved objective and productive coordinator decision. This discrepancy did not alter termination, lose evidence, or create a subsequent-research continuity defect. Existing research-session regression coverage already exercises the same unresolved-stop/achieved-objective transition. No SIGMA correction is warranted.

The baseline's turn-2 false missing-input critique is attributable to the T146 evaluation harness: the frozen task includes all eligibility and precedence data and was sent in turn 1, but the preserved stateless turn-2 request contained only the prior assistant answer and the turn instruction, with no task payload or prior-response chain. The harness caused missing context; the response is not evidence of spontaneous model failure while the full task was present. T146 evidence remains untouched. No benchmark-specific harness change was made; future comparisons must correct and freeze/hash context continuity before separately authorized use.

[Full diagnosis](evaluations/increment_23/diagnosis.md). Verification: `./sigma test` ran the full offline lifecycle through Ruff, format, Pyright (0 diagnostics), and frontend typecheck; the three existing T128 deployment assertions failed because they expect `srv-sigma\\x2dstate.mount` while current `main` uses `RequiresMountsFor=/srv/sigma-state`. The suite skipped frontend production build after those failures. The research-session scenario passed, including the unresolved-stop/achieved-objective regression. `git diff --check` and all 12 frozen T146 manifest hashes passed. No browser workflow changed. No provider calls or Cloud operations occurred.

## Issue #119 — longitudinal research evaluation design (2026-10-26)

Started from current `main` at `537c198` after PR #150/T146 and PR #164/T147 merged. Read issue #119, the merged evidence and diagnosis, and the existing T114/T118 and Increment 21 evaluation framework. No paid inference was authorized or performed.

The existing production-path offline tests demonstrate durable context assembly, source attribution, cross-session artifact reuse, failed/completed computation provenance, explicit cross-strategy continuation, and refusal of foreign, truncated, stale, or misrepresented evidence. Focused checks `tests/epistemic_continuity.py`, `tests/continuations.py`, and `tests/research_feedback.py` passed. Their model outputs are scripted, so they establish orchestration and persistence mechanics only. T146 was one within-session cycle; T147 shows its baseline arm omitted the original task on turn 2. Neither is longitudinal comparative-quality evidence. No reproducible SIGMA product defect was found.

Added [issue #119 longitudinal design](evaluations/issue_119/longitudinal-design.md): a proposed six-task-family, three-session, branching-evidence 2×2 factorial separating role organization from history availability, with a full-history single-role comparator receiving equivalent persistent evidence and tools. It specifies continuity, evidence use, branching, negative-result retention, repetition, final-quality, calibration, cost, blinding, and integrity measures. At two repeats/task/condition and two calls/session, the draft would require up to 288 call attempts. This is a small exploratory design (`n=6` task clusters), not frozen or authorized. Tasks, keys, provider/model settings, caps, independent curation/grading, information-equivalence review, and approval remain open.

This was a protocol/design review only: no actual project was exercised, so no project export or browser acceptance artifact applies. No Cloud changes, product changes, or provider calls occurred. `./sigma test` ran through all research continuity, continuation, and feedback scenarios, plus Ruff, formatting, Pyright (0 diagnostics), and frontend typecheck. It exited 1 on the same three T128 mount assertions in `tests/deployment_package.py`, `tests/gce_host.py`, and `tests/host_monitor.py`; the frontend production build was skipped after failures. The three focused commands also passed independently: `uv run --locked --no-sync python tests/epistemic_continuity.py`, `tests/continuations.py`, and `tests/research_feedback.py`. `git diff --check` passed. No browser path changed.
# T172 — Pre-deployment authentication and account-isolation gate (2026-10-26)

**Readiness: BLOCKED for production launch.** Reviewed integrated T66/PR #169,
T131 and T134 implementation, tests and evidence. These tickets were closed as
offline implementation/preparation only; hosted OAuth and real two-identity
privacy acceptance were explicitly deferred. The full findings, exact required
OAuth settings, first-live-sign-in checklist and remaining real-identity gaps
are in [T172 assessment](T172_AUTH_READINESS.md).

No new launch-blocking code defect was identified in this offline review.
Server-side Google OAuth state/nonce/claim checks, origin protection, session
expiry/revocation, owner-bound persistent workspaces and hosted personal
ChatGPT-auth rejection have deterministic coverage. Production launch is still
blocked until an owner-authorized hosted run verifies the production OAuth
client/secret delivery, real admin/member/denied identities, HTTPS callback,
deployed session behavior, T131 sign-in/denial matrix, T134 two-user privacy
matrix, and hosted persistence/recovery. Any disclosure, stale access, or
cross-owner mutation during that run blocks launch. No live OAuth, provider
calls, production credential changes, infrastructure provisioning or policy
changes occurred.

Assessment checks:

- `tests/cloud_auth.py`: PASS (16 tests); `tests/cloud_workspaces.py`,
  `tests/cloud_research.py`, `tests/cloud_research_api.py`,
  `tests/cloud_research_sponsored_api.py` and `tests/storage.py`: PASS under
  `./sigma test`.
- `uv run --locked --with playwright python
  browser_checks/t23_1_google_signin.py`: PASS in real Chrome against local
  fixture identities and temporary storage; no external Google request.
- `./sigma test`: FAIL overall. The first run passed the authentication, storage
  and owner-isolation scenarios but hit three existing deployment assertions in
  `tests/deployment_package.py`, `tests/gce_host.py`, and `tests/host_monitor.py`:
  tests expect `srv-sigma\\x2dstate.mount`, while the current unit uses
  `RequiresMountsFor=/srv/sigma-state`. Frontend `tsc` was initially absent;
  after `npm ci --prefix frontend`, frontend typecheck and production build
  passed independently. Build was skipped by `./sigma test` after earlier
  failures. A second run with other checkouts executing broad tests concurrently
  additionally hit a `tests/research_sessions.py` shared worker-active lock;
  the focused auth/workspace/storage scenarios still passed.
- `git diff --check`: PASS. No authentication source or T163 files changed.

## T131 — Production Google OAuth configuration readiness (2026-10-26)

Reviewed current `main` at `a335f3f`, T172's auth audit, T131's hosted OAuth
acceptance procedure, the operations/deployment runbooks, Compose wiring,
read-only GCE preflight, secret fetch helper and auth implementation. Added the
[T131 production readiness checklist](T131_PRODUCTION_OAUTH_READINESS.md)
with exact project/consent/client/origin/callback/scope settings, secret and
runtime IAM requirements, bootstrap/member setup, observed fail-closed auth
behavior, escalation rules and the first-live-sign-in acceptance procedure.

Evidence remains preparatory: the runbook identifies `SIGMA Auth`
(`sigma-auth-512601`) as an existing OAuth project but leaves production client
project selection unresolved. Its 2026-10-25 checkpoint says the OAuth Secret
Manager secret was not created because an initial version was required. Secret
payload, active version, resource-scoped `roles/secretmanager.secretAccessor`
binding, deployed environment/client ID, bootstrap/member grants and hosted
status have not been inspected. The runbook records DNS/external IP verification
pending; the coordinator and human are independently checking it, so no DNS
correctness is assumed. Actual HTTPS callback and Google consent configuration
remain unverified.

No OAuth client, consent screen, IAM, secret, production environment, DNS,
infrastructure, identity or hosted endpoint was modified or exercised. No
Google OAuth, provider call, or personal ChatGPT auth occurred. `./sigma test`
ran and **failed overall** on the existing deployment contract mismatch in
`tests/deployment_package.py`, `tests/gce_host.py`, and `tests/host_monitor.py`:
the assertions still expect `Requires=docker.service sigma-sandbox.service
srv-sigma\\x2dstate.mount`, while the current `deploy/systemd/sigma.service`
uses `RequiresMountsFor=/srv/sigma-state`. Research scenarios, cloud auth
(16 tests), storage/cloud workspace/research scenarios, public endpoint (7
tests), Ruff check/format, Pyright (0 diagnostics), and frontend typecheck
passed. The frontend production build was skipped after earlier failures. No
real-browser check was run because no browser workflow changed; fixture and
Chrome evidence remains the previously recorded T172 result, not this hosted
configuration review. `git diff --check` is recorded in the handoff.

## T163 — Integrate local UI regressions on current main (2026-10-26)

Integrated the missing T163 create-request and default local ChatGPT corrections
onto `main` at `8e8d979`. Current `main` already contained the strategy-derived
state memoization from PR #168, so that fix was retained without duplicating a
change. Project creation now sends the default `show_advanced_outcome_details`
value, the strict API accepts it, and the shared creation service persists it.
The local ChatGPT sign-in gate now applies only when local authentication is
enabled; hosted service-funded connection behavior remains separate.

Verification: `tests/project_creation.py` and all 16 `tests/cloud_auth.py`
scenarios passed. Real Chrome checks passed for project creation/default local
connection, configured local OAuth sign-in and identity isolation, local versus
hosted connection UI, and strategy/session controls without a React render
loop. The strategy browser uses deterministic AI configuration fixtures and
intercepts session start; no provider call is made. `npm --prefix frontend run
build` passed (existing Vite chunk-size advisory). The first `./sigma test`
run on base `8e8d979` failed three deployment mount assertions in
`tests/deployment_package.py`, `tests/gce_host.py`, and `tests/host_monitor.py`.
After merging PR #181's test reconciliation with current `main` (`8acb54a`),
`./sigma test` passed all scenarios, deployment checks, Ruff, format, Pyright
(0 diagnostics), frontend typecheck, and frontend build. The four real-Chrome
checks were rerun on the updated base and passed. No cloud, OAuth-provider, or
AI-provider operation was performed.

PR #168 supplied these changes against its old base but is no longer suitable
for integration because its changes conflicted with current `main`. Its render
loop fix is already in `main`; the remaining corrections are carried by the
fresh-base T163 PR. Close #168 after the replacement PR is merged so its
discussion and verification record remain available through that interval.

## T129 — Release-image SHA correctness and reproducibility (2026-10-26)

Confirmed the release mismatch: production Compose selected image tags from
`SIGMA_RELEASE` while retaining a `build:` context rooted at the mutable
`/opt/sigma/current` checkout. `start-gce.sh` ran Compose `up` without
`--no-build`, so startup could build working-tree contents and still apply the
operator's requested SHA tag. The operator runbook did not bind image contents
to that SHA. Rollback changes the same SHA pin and preserves existing state,
preflight, restart and health gates.

Added `deploy/release_image.py`: it accepts only a full lowercase commit SHA,
requires Git to resolve that exact object, exports the commit tree via
`git archive`, and builds both `linux/amd64` images from the exported context
with an OCI source-revision label. Production startup verifies both image
labels before Compose, uses `up --no-build`, and records the source SHA,
container IDs, actual immutable image IDs and available repository digests
under `/var/lib/sigma/releases/SHA.json`. Rollback candidates without matching
provenance labels fail closed. Deterministic tests cover a dirty tree with a
different HEAD, unresolved/malformed SHA, source-label mismatch, and digest
recording. The storage startup fixture now supplies a deterministic release
pin and stubs the verifier.

Focused checks passed: `tests/release_image.py` (3 tests), `tests/storage.py`,
Ruff check/format, Pyright (0 diagnostics), frontend typecheck, `bash -n
deploy/start-gce.sh`, and `git diff --check`. `./sigma test` ran the full
suite but exited 1 on three pre-existing systemd dependency assertions in
`tests/deployment_package.py`, `tests/gce_host.py`, and `tests/host_monitor.py`;
they expect `srv-sigma\\x2dstate.mount`, while current `main` uses
`RequiresMountsFor=/srv/sigma-state`. All other scenarios passed. Frontend
production build was skipped by the suite after those failures. No live cloud
operation, deployment, paid provider call, or browser workflow was performed.

Offline implementation is R4R in [PR #182](https://github.com/bkramerext/sigma/pull/182);
the full evidence handoff is in [T129 Gray handoff](../messages/t129_gray_release_sha.txt).
Hosted release behavior and rollback with actual production images remain
unverified.

## T170 — pre-deployment research workflow acceptance (2026-10-26)

Started from current `main` at `b33e9945ec2c18d149ad5e8a45b2da6fa70849b9`.
Overall assessment: **BLOCKED for production go/no-go; PASS for the scoped
local simulated workflows**. Project creation/session lifecycle, evidence
continuity, Outcomes/reports, and Markdown/TeX/PDF exports passed deterministic
and packaged Chrome checks. Local Colima Python and Sage execution passed
isolation probes; production rootless daemon acceptance remains blocked. The
T91 packaged Chrome run also verified backend recreation, fresh-volume restore,
and simulated-account isolation. No live provider use, paid call, or GCE action
occurred.

The acceptance report and captured app exports are in
[T170 evaluation evidence](evaluations/t170/README.md). The existing T91
browser check now accepts optional `SIGMA_T91_EVIDENCE_DIR` to retain actual
downloaded audit/report bytes plus fixture TeX/PDF and a source-ID/hash
manifest; the default temporary behavior is unchanged. No deterministic
product regression gap was found, so no duplicate T99/T137 test or product
behavior was added.

`./sigma test` **failed** three existing deployment assertions in
`tests/deployment_package.py`, `tests/gce_host.py`, and `tests/host_monitor.py`:
they expect the old escaped `srv-sigma\\x2dstate.mount` dependency, while
current `main` uses `RequiresMountsFor=/srv/sigma-state`. Ruff passed, Pyright
reported zero errors/warnings, and frontend typecheck passed; the frontend
production build was skipped by the test runner after the failures. Relevant
research/session, continuity, Python/Sage contract, report/paper, T99 sponsored
API, workspace, and storage steps passed during the same run.

`uv run --locked --no-sync python -m sigma.cloud_runtime_check --allow-nonrootless-dev`
passed Python and Sage container probes (UID 65532, host files/state/network/
Docker socket blocked; captured artifacts persisted). The daemon reported
`daemon_rootless: false`, so this is local Colima evidence only. Both
`bash deploy/validate-local.sh` and the run with `SIGMA_T91_EVIDENCE_DIR` passed
real Chrome against packaged Compose; the latter retained audit JSON, text and
HTML reports, TeX, and a parsed PDF with hashes. OAuth and inference were
skipped. No production instance was provided, and T137 remains blocked on
hosted acceptance and coordinator/owner go-no-go. Work completed in about 24
minutes, ahead of the 45-minute target.

## T170 / T173 current-main acceptance follow-up (2026-10-26)

T170/T173 acceptance evidence was gathered on `main` `8e8d979`; PR #183 was
subsequently updated through `main` `8acb54a` after Red's T128/PR #181 and
T130/PR #185, then through current `main` `4f0339a` after Green's PR #184.
The review covered the T129/T130/T135/T136 release controls, T132/T133 workflow evidence, T137 launch gate, T171 host audit,
T172 auth gate and T131 OAuth checklist. No paid calls or cloud changes were
performed. The application is not deployed; public HTTPS currently serves the
temporary readiness page as supplied in the assignment.

Corrected the three stale deterministic systemd assertions in
`tests/deployment_package.py`, `tests/gce_host.py`, and `tests/host_monitor.py`:
current `deploy/systemd/sigma.service` declares `RequiresMountsFor=/srv/sigma-state`
with Docker/sandbox requirements and ordering, rather than spelling the
escaped mount-unit dependency directly. This changes tests only. `./sigma test`
now passes end to end, including Ruff, format, Pyright (0 diagnostics), frontend
typecheck and production build.

Current acceptance evidence is recorded in [T170](evaluations/t170/README.md)
and [T173](evaluations/t173/README.md). Real Chrome against disposable packaged
Compose passed project/strategy editing and reopen, saved sessions/Outcome,
audit/text/HTML exports, fixture TeX/PDF compilation and download, backend
restart, container recreation, fresh-volume restore, report/paper/session hash
continuity, and simulated second-user isolation. Python and SageMath runtime
probes passed in local Colima containers (UID 65532; host secret/state, network,
and Docker socket blocked), but daemon rootless status was false. A disposable
Linux fixture ran the real rollback helper's failed-health and healthy branches;
the failed branch restored the old SHA, and both branches preserved a state
sentinel. No failed image-build injection was run.

**Readiness remains BLOCKED** for production. The failed-build path and actual
GCE/systemd rollback, target-host rootless isolation, persistent-disk backup and
restore, reboot, hosted HTTPS/API app checks, production OAuth/admin/member/
rejected identities, workspace isolation, and any provider-backed session need
owner-authorized live acceptance. The runbook requires a verified recovery point
and schema-compatibility assertion before code rollback; restore and code
rollback are separate. No application was deployed and no T137 go/no-go was
made.

## Coordinator integration — cloud deployment PRs (2026-10-26)

- PR #180 merged as `0fb0587`: the three deployment tests now assert the current `RequiresMountsFor=/srv/sigma-state` systemd contract. Blue's exact-main evidence remains in `docs/evaluations/increment_6/`.
- T128 host-readiness implementation, T128 blocked-live assessment, and T173 release rehearsal are being consolidated on `coordinator/cloud-pr-integration` so the stale PR bases do not discard newer `main` work.
- T129 deployment integration now calls `deploy/release_image.py build` for the exact requested SHA, checks image source labels, and records verified image IDs/digests after successful startup. This specifically addresses the T173 finding that a tag could otherwise misrepresent the source tree.
- No live GCE operation, production secret access, OAuth operation, or provider call occurred during this integration. Hosted readiness remains blocked until the operator verifies GCE access, host/disk/firewall state, production OAuth configuration, and first-start acceptance.

## Issue #98 — Gray release-integrity review (2026-10-25)

Reviewed current integrated `main` at `dd23fec65683cea72b39f95f952377cc41a84346` (PR #195). The working checkout was not used as the review baseline. Independently inspected T129 release-image automation, GCE deploy/start/rollback scripts, Compose, systemd ordering, backup/restore tooling, runbook requirements, and the integrated T173 rehearsals.

The release builder resolves a full lowercase 40-character commit, exports that exact Git tree, builds both application images with the source-revision label, verifies the labels before startup, and records the running container IDs, immutable image IDs, and available repository digests. The systemd startup path requires Docker and the rootless sandbox service, orders them before SIGMA, and requires the persistent state mount. Compose waits for healthy backend/frontend before edge; startup uses `--no-build`. Rollback requires explicit backup/schema assertions, a mounted state disk, no active backup, and locally available images; it restores the previous release pin and attempts the prior service after candidate preflight/start/health failure without editing application state. The backup service stops writers, verifies Compose containers are gone, waits for a READY snapshot before retention pruning, and records failure/restart outcomes. Restore verification is read-only against a separate disk clone.

No release-engineering code correction was indicated by this offline review. Source-SHA labels and image IDs provide auditable local provenance; no cryptographic image signature or reproducible-build guarantee is claimed. Production release acceptance remains BLOCKED: no live VM was accessed, and actual GCE startup/rollback, rootless-host isolation, production backup/restore, hosted OAuth/access isolation, and public HTTPS/API checks remain owner-authorized gates. No services, paid calls, or production credentials were used.

Focused checks passed: `tests/release_image.py` (3), `tests/deployment_automation.py` (including injected startup failure and persistent sentinel preservation), `tests/state_backup.py` (8), shell syntax checks for startup/rollback/backup, and `git diff --check`. The first `./sigma test` run stopped at frontend typecheck because clean-worktree `node_modules` was absent. After `npm ci --prefix frontend`, the full `./sigma test` passed: lifecycle/deployment/cloud scenarios, T173 failed-build and source-SHA rehearsals, Ruff, formatting, Pyright (0 diagnostics), frontend typecheck, and production build. No real-browser run was needed because no UI changed; no live deployment checks were attempted.

Evidence handoff: [Gray issue #98 release-integrity review](../messages/t98_gray_release_integrity.txt).

## SIGMA hosted preview follow-up: issues #201–#202 (2026-10-26)

Research-session admission now refuses to create a session when prior-session
unresolved obligations exceed the frozen context bound. The error lists the
omitted obligation IDs and points to a focused continuation or strategy-narrowing
recovery path; previous sessions and evidence remain intact. Context, evidence,
and spend safeguards remain enabled. Sponsored cloud sessions now use the
administrator-enforced $0.25 cap independently of a user's API-key spending
limit; the user cost control is hidden in hosted settings and remains available
for local/API-key billing.

Paper snapshot hashing now excludes the dynamically computed `elapsed_seconds`
projection while retaining saved session and evidence fields. A concurrent
durable evidence change still conflicts. A typed preflight conflict reports
`provider_calls_attempted: 0`, so the browser no longer claims that a provider
request may have completed in this known pre-dispatch case. Saved paper versions
and evidence are not changed by the conflict.

Verification on `main` plus the issue branch: `./sigma test` passed all
scenarios, Ruff, formatting, Pyright (0 diagnostics), frontend typecheck and
production build. Focused paper snapshot/version/API conflict, obligation
overflow recovery, and sponsored-budget tests passed. Real Chrome model-control
acceptance passed at desktop and mobile sizes with injected 401, 403, and 503
catalog failures; settings remained unchanged, model/thinking stayed disabled,
and no inference was made. No paid provider calls or production changes were
performed. PR #207 and PR #208 are merged. Issues #201–#202 remain open pending
hosted workflow acceptance against the supplied persisted project; #202 also
requires explicit authorization before any paid hosted generation. Issue #200
remains open pending an authenticated hosted availability request and server
evidence to identify the underlying failure.

## Issue #206 — Current Understanding presentation (2026-10-26)

Current Understanding now uses the established copper/black visual hierarchy,
a visible native disclosure chevron, and an expanded-by-default disclosure. The
redundant saved-session count was removed from its heading; the separate session
pane count remains. Research synthesis, evidence links, and navigation logic
were left intact. The layout was checked at 1440, 390, and 320 pixels.

Focused real Chrome verification and the frontend typecheck/build passed. The
full browser check still fails while focusing a linked research artifact; the
same failure occurs on unmodified `main` (`2c409e6`). `./sigma test` remains
blocked by Ruff findings in `browser_checks/model_availability.py` on `main`
(B023 and formatting); this change did not modify that file. No provider calls
were made. See [Gray issue #206 handoff](../messages/t206_gray_current_understanding.txt).

## T43.2 / issue #66 independent release acceptance (2026-10-26)

Integrated acceptance ran on a Gray branch containing T88 merge
`e82152010c81c53a84753fdbcc323628e16dfeae`. Deterministic API tests passed for
guest denial, invited/admin roles, grant revocation and expiry, owner-scoped
workspaces and research artifacts, sponsored provider status, and user budget
enforcement. A focused sponsored API assertion now confirms administrators
receive the same $0.25 per-user allowance as members. The Google Chrome fixture
passed guest/member/admin transitions, provider failure/recovery, sign-out,
denial, remembered-project clearing, and desktop/mobile layouts. Separate
two-user Chrome and ChatGPT SIWC fixture checks also passed.

`./sigma test` passed all scenarios, Ruff, formatting, Pyright, frontend
typecheck, and build. The first run encountered transient research-worker lock
contention; the isolated scenario passed, followed by a complete passing run.
The existing >500 kB chunk advisory remains. Actual Google OAuth, hosted
callback/deployment/session behavior, live provider authorization, and
distinct-live-account workspace isolation remain **UNVERIFIED**. No live GCP,
OAuth/provider calls, paid inference, credentials, or private user data were
used. Full requirement-by-requirement evidence is in
[T43.2](../tickets/t43.2.md) and the
[Gray handoff](../messages/t43_2_gray_multi_account.txt).
## Issue #209 — Copy-only strategy suggestions (reconciled 2026-10-26)

PR #213 was reconciled with Gray PR #212 at `6bab28f`. The resulting interface
preserves the copper Current Understanding heading, visible chevron,
default-expanded disclosure, and session count placement, with Suggest a
Strategy nested after the synthesis. Suggestions remain ephemeral, safe
collapsible Markdown copied through SIGMA's shared clipboard control. Historical
continuation data remains readable; research-session lifecycle, evidence
navigation implementation, strategy editing, provider authorization, cost
limits, and bounded context safeguards were retained.

Focused proposal tests, Ruff for changed files, Pyright, frontend typecheck and
build passed. Real Chrome's focused header/suggestion check passed at 1440, 390,
and 320 pixels. The broader Chrome check passed the disclosure and suggestion
flows, then failed at the existing linked-artifact focus assertion; evidence
navigation/export portion did not complete. `./sigma test` ran all scenarios,
then exited 1 at repository Ruff B023/formatting findings in unchanged
`browser_checks/model_availability.py` (same file as current main). The separate
frontend build passed. See [Issue #209 handoff](../messages/issue_209_green.txt).

## T81 — Invitation Requests, Feedback, and Privacy (2026-10-26)

Replaced the denied-access screen's mail draft with a POST to the hosted auth
backend. The request is keyed to the Google subject from the server's
short-lived verified-denial record; a caller-supplied email is ignored. The
durable auth database stores Google subject, verified email, request timestamp,
notification status, and a non-sensitive delivery-failure marker. Repeated
requests for one Google subject are idempotent, including concurrent
submissions through a persisted delivery claim; a verified email is limited to
three new requests per 24 hours. Non-admin users cannot read or update the
administrator request list. Admins can mark requests reviewed or declined in
Administrator Settings.

Successful delivery replaces the button with the exact requested static
message. Backend errors retain the button and display an error. Email is sent
over TLS SMTP with authenticated login, a sender derived from the authenticated
mailbox account, and fixed recipient `zetacontinuation@gmail.com`. Deployment
composition and Secret Manager fetch/preflight handling now include the
protected SMTP credential.

`tests/cloud_auth.py` passed (23 cases), including spoofed-body identity,
unauthorized admin access, idempotency, per-email rate limiting, retryable
delivery failure, concurrent duplicate suppression, admin review, and SMTP authentication/sender/recipient
checks. Real Chrome accepted the denied-screen POST, exact static success
message, desktop/mobile layouts, and administrator review list. `./sigma test`,
Ruff, formatting, Pyright, frontend typecheck/build, `tests/gce_host.py`,
`tests/deployment_package.py`, Python compilation of the browser check, and
`git diff --check` passed.

No authenticated SMTP credential is provisioned in this checkout and no live
email or hosted deployment was performed. Production notification delivery
remains dependent on creating the approved SMTP Secret Manager resource and
configuring the account identity in deployment settings. No mail credential
was added to source control. Reconciled with current main
(`90fab8cbd5293d4cf4e0bad07b161a8c5d409f86`) at validated integration commit
`6f90d3f49bbb324b3e8d953bfe1b92ed293c12d3`; GitHub reports PR #225 open,
non-draft, and mergeable. The post-reconciliation `./sigma test`, Ruff check and
format, Pyright, frontend typecheck/build, and real Chrome invitation/auth check
all passed. The Chrome scenario exercised verified-denial submission, success,
account switch, Demo handoff, local Home, and administrator review. No live SMTP
credential or delivery was available. See the updated T81 handoff.

## T192 — Per-User Project Isolation (2026-10-26)

Audited the current-main Google OIDC subject-to-workspace flow, protected API
dependency, project path resolver, authenticated project services, reports,
papers/downloads, research execution artifacts, and Docker/Sage sandbox
configuration. Existing implementation derives durable workspace mappings from
the verified Google `sub`; no server-side identity header or caller-selected
workspace ID controls project ownership. Local-mode project storage and Recents
remain unchanged. Reused T43.2 / PR #222's independent release acceptance for
fixture account switching and its broader browser acceptance; its explicitly
unverified live OAuth boundary remains.

Added cross-owner API regressions for project metadata update, text-source
evidence writes, and research execution creation. Guessed victim paths are
rejected with the same not-found response; project bytes and prior execution
records remain unchanged, and no text-source directory is created. Existing
tests continue to cover guessed IDs, strategy/session/evidence/report/paper and
export reads, downloads, traversal and symlinks, forged headers, SQLite mapping
durability, filesystem permissions, restart/restore, and unmounted sandbox
commands.

`python tests/cloud_workspaces.py`, `python tests/cloud_auth.py`,
`python tests/python_sandbox.py`, and full `./sigma test` passed. The full run
included Ruff, formatting, Pyright (0 diagnostics), frontend typecheck and
production build. The build retains the existing >500 kB chunk advisory. No
production deployment, live OAuth, paid inference, or provider calls occurred.
Production OAuth/account switching, hosted mount permissions, revocation, and
runtime sandbox isolation still need live production verification; they were
not tested under this assignment's constraints. See [T192](../tickets/t192.md).
Implementation and regression tests are in [PR #223](https://github.com/bkramerext/sigma/pull/223), open against `main` and not merged.

## Issue #200: hosted model checks and explicit ChatGPT sponsor

Authenticated production testing identified the blanket hosted `/api/ai/` 403
while Google admin authentication succeeded. Read-only authenticated model and
connection checks now reach the provider; hosted account-changing/OAuth routes
remain blocked. An explicit ChatGPT sponsor mode uses a dedicated persistent
credential store pinned to the verified sponsor email. Protected import retains
the VM host ID, imports only the selected registration, and preserves prior
state on rejection. Existing serialized refresh and cloud admission guards
remain in use. ChatGPT mode never falls back to local accounts or API billing.

Focused checks passed: sponsor (8), cloud auth (24), GCE host (21), and sponsored
API workflow. Ruff/format, Pyright (0 diagnostics), and frontend build passed.
The full suite is limited by AF_UNIX socket creation denied in this environment;
`instance_ownership.py` and `ui_registry.py` reproduce that failure on unchanged
main `e62d808`. Chrome installation download failed, so this branch has no local
real-browser acceptance. No production change, credential transfer, or inference
was performed. See [handoff](../messages/issue_200_sponsor_fix.txt) and
[provisioning procedure](T200_SPONSOR_CONNECTION.md). Live sponsor provisioning,
deployment, catalog verification and #201/#202 original-project retests remain
UNVERIFIED; issue #200 remains open.

The #200 dispatch follow-up replaces API-key-only inference guards with a shared
explicit-provider validator across research, proposals, agentic generation,
papers and text conversion. ChatGPT-funded cloud research keeps estimated-cost
accounting and durable admission reservations. The production API fixture passes
in both API-key and ChatGPT SSE modes, including completed six-call sessions,
saved Outcomes/exports, budget exhaustion, failure holds and owner isolation.
No live provider inference was used for these tests.
## Issue #228 — Sponsorship allowance column alignment (2026-10-26)

Renamed the authorized-users column to **Sponsorship Allowance** and centered its
heading, currency/input unit, and effective-allowance text on the same column
axis. Preserved the four-column widths, copper/navy colors, and existing
horizontal scroll behavior. No allowance or backend behavior changed.

Real Chrome check `uv run --with playwright python
browser_checks/issue228_sponsorship_allowance.py` passed at 1440px and 390px.
It verifies the exact heading, absence of the old heading, column-center
alignment, effective amount, horizontal scrolling at 390px, and no page-level
horizontal overflow. Screenshots: `/tmp/sigma-issue228-admin-1440.png` and
`/tmp/sigma-issue228-admin-390.png`. `./sigma test` passed, including Ruff,
formatting, Pyright (0 diagnostics), frontend typecheck, and production build;
the build reports the existing >500 kB chunk advisory. The test used only
deterministic local fixtures; no provider calls or costs occurred. See the
[issue #228 handoff](../messages/issue228_gray_sponsorship_allowance.txt).
Implementation is in [PR #232](https://github.com/bkramerext/sigma/pull/232),
open against `main`, current and mergeable, and not merged.

## Guest sample projects and About privacy actions (2026-10-26)

Guest Home now uses the normal Projects layout and existing sample catalog;
New/Open project actions are hidden. The normal Recent/Samples toggle is present, Recent is
selectable, and Samples is selected by default. Selecting Recent shows only the
static, two-line message “Sign in to create and / save your own projects.”
styled with the Projects header font at a smaller size; it does not
load or save project history. Recent and sample groups start collapsed. Opening
or creating a guest project uses
an opaque eight-hour, in-memory guest session and a private temporary workspace.
The project path resolver confines access to that workspace, guest Recents are
always empty, and expired workspaces are cleaned up on later guest requests.
Guest sessions cannot run provider-backed research, paper/proposal generation,
or AI text conversion. The Guest sign-in pill uses the normal Google sign-in
dialog and link. Guest attempts to generate a strategy receive a clear
signed-in-account message; the temporary project remains available. The TeX
dialog tells guests “Sign in to export your research as TeX.” without requesting
paper data. The guest UI no longer makes personal model or catalog requests that
produced misleading authentication-error toasts.

The separate Guest welcome panel is removed; Projects appears in the same Home
location as for signed-in users. Browse Published Research is absent for guests.
The About dialog keeps Privacy Policy as a lower-left action button, the policy
page has a Return to SIGMA action at the top, the Google pill copy is shorter,
and artwork credit reads “Brian Kramer” / “& GPT Models”.

Verification: `uv run python tests/cloud_auth.py` passed (29 tests), including
guest sample opening with configured and unready Google Auth, temporary path
containment, empty Recent, and blocked provider-backed routes. Changed-file
Ruff check/format and Pyright passed. The
real Chrome flow `uv run --with playwright python browser_checks/guest_samples.py`
passed the standard Projects Home, guest Recent static message without a Recent
request, default Samples selection and collapsed groups, normal Google sign-in
action, TeX guest message without paper API requests, Generate feedback, sample open
into the full workspace, no 401 toast, empty Recent, and both privacy actions.
Frontend typecheck and production build
passed; build retains the existing >500 kB chunk advisory. No provider calls or
costs occurred.

`./sigma test` completed with four repository checks failing outside the guest
change: `tests/tooling.py` expects the admin-contact warning; Ruff reports four
issues in `src/sigma/gmail_delivery.py` and `tests/gmail_delivery.py`; format
check reports existing formatting in `src/sigma/cli.py`, `src/sigma/gmail_delivery.py`,
`src/sigma/ui_instance.py`, and `tests/gmail_delivery.py`; Pyright reports
`tests/gmail_delivery.py:56` accessing `.decode` on `Message[str, str]`. The
frontend typecheck and all guest-focused checks passed. The build step was
skipped by `./sigma test` after those failures and was run separately
successfully. See the [Blue guest-samples handoff](../messages/guest_samples_blue_r4r.md).
Implementation is in [PR #246](https://github.com/bkramerext/sigma/pull/246),
open against `main` and not merged.

## ChatGPT authentication guidance copy (2026-10-26)

Updated the existing ChatGPT connection guidance to distinguish a user with no
connected ChatGPT account (`disconnected`) from a saved account requiring
interactive recovery (`reauth_required`). The first is told “Research requires a
ChatGPT connection. Sign in to continue.”; the second is told “Your ChatGPT
session has expired. Please sign in again to continue.” The state distinction
comes from the existing auth snapshot: no active account versus a retained
account record that needs reauthorization. No credential, authentication, or
research persistence behavior changed.

Focused verification: `uv run python tests/chatgpt.py` passed. Ruff check,
format, and Pyright passed for `src/sigma/openai_connection.py` and
`tests/chatgpt.py`. `./sigma test` ran to completion but retained four known
failures: the admin-contact warning assertion; four Gmail delivery Ruff
findings; formatting in Gmail delivery, CLI, UI instance, and the previously
committed `browser_checks/guest_samples.py`; and the Gmail test `.decode`
Pyright error. All ChatGPT tests passed during the full run. The frontend
typecheck passed; the full runner skipped its build after failures. No
authentication flow, credentials, or saved research were changed. Handoff:
[`messages/blue_chatgpt_auth_messaging_r4r.md`](../messages/blue_chatgpt_auth_messaging_r4r.md).
The change is included in [PR #246](https://github.com/bkramerext/sigma/pull/246)
against `main` due to overlap with the active Guest connection UI branch; it is
open and not merged.

## Guest research-session Play sign-in prompt (2026-10-26)

Guest Play now opens an accessible “Ready to investigate?” dialog with the
message “Sign in to run a research session. You can explore sample projects as a
guest.” The “Sign in now” action opens the existing Google sign-in pill, whose
Google link starts the established login workflow. “Cancel” and Escape dismiss
the dialog and restore focus to Play. Guests can activate Play
even when normal session-start preconditions would disable it, but that path only
changes dialog UI state. It does not call the research start handler, read
provider configuration/limits, reserve budget, or mutate the project. Signed-in
Play continues to use the existing handler.

Verification: `uv run --with playwright python browser_checks/guest_samples.py`
passed in real Chrome, including assertions that Play, opening the Google
sign-in pill, and Cancel issue no
research/configuration/limits requests or write requests, and that focus returns
to Play. Frontend typecheck and production build passed. `./sigma test` ran to
completion; all reached tests including ChatGPT and cloud auth passed, while
four pre-existing checks failed: the admin-contact warning assertion, Gmail
delivery Ruff findings, formatting in CLI/Gmail/UI instance files, and the
Gmail test `.decode` Pyright error. The suite skipped its build after these
failures; the standalone production build passed. Handoff:
[`messages/blue_guest_play_signin_r4r.md`](../messages/blue_guest_play_signin_r4r.md).
The change is included in [PR #246](https://github.com/bkramerext/sigma/pull/246)
against `main` on the active Guest implementation branch; open and not merged.
## Issue #200 reconciliation with current main

PR #230 reconciled with main `6a607a4`; both #200 and #228 status records and
all main invitation/Gmail/guest changes were preserved. Hosted personal
ChatGPT credential work remains Green's T88 scope. Current guest-startup test
expectations and inherited Ruff/type-check failures were corrected without
changing launcher or invitation behavior. Focused sponsor, cloud-auth, GCE,
Gmail and dual-provider research API tests, frontend typecheck/build, Ruff and
Pyright passed. The model-availability and Recent Chromium workflows passed;
Research Outcome passed on the merge tree. Full local verification was limited by the environment denying AF_UNIX sockets;
GitHub SIGMA verification run 40399333103 passed on validated code head
`aea3365434a3c5fb708749724c132d303649815b`. Hosted sponsor provisioning and
acceptance remain unverified. See the issue #200 handoff.

## T201 local obligation recovery follow-up (2026-10-26)

The local overflow admission check reports bounded obligation IDs and excerpts for
large histories, preserves saved research, and guides users to fork from a saved
session while disabling the over-limit original. Blocked attempts no longer reserve
session numbers. Focused regression uses a disposable project and fake provider;
see [the T201 handoff](../messages/issue_201_local_recovery.txt). Original hosted
project acceptance remains unverified; local acceptance is the T201 closure criterion.

## PR #246 — guest integration with current main (2026-10-26)

Integrated `origin/main` at `48fe9a1fee87a23c1af1665f1f30723ef39d9e97` into
the Guest branch in merge commit `9743cd704b8a97a50b8187877c1464f988818e42`.
The merge's only conflict was in this status file; both the Guest history and
T200 reconciliation were retained. Source and test changes from main merged
without conflicts. Guest Play's “Sign in now” Google pill handoff, “Cancel”
behavior, and guest no-dispatch/no-mutation constraints passed real-Chrome
acceptance after the merge. `tests/cloud_auth.py` (30 tests), `tests/chatgpt.py`,
frontend typecheck/build, and focused Guest Ruff checks passed. `./sigma test`
passed all steps, including Ruff, formatting, Pyright (0 diagnostics), typecheck,
and build. Main's T200 integration also resolves the four earlier repository
baseline failures. Existing >500 kB frontend chunk advisory remains. PR #246 is
returned open for review; it has not been merged. See the [updated Blue
handoff](../messages/blue_guest_play_signin_r4r.md).

## PR #246 — browser acceptance for collapsed sample groups (2026-10-26)

Updated T92 Recent Projects and T200 Model Availability browser checks to
expand the Mathematics sample group before locating/clicking its sample. T92
also expands the Recent Mathematics group before locating the opened project,
including after reload. Product UI defaults are unchanged; sample groups still
start collapsed. Correction commit:
`56cdbdf65a56d025d15b1192dd19b0a4aa65be3d`.

Both requested workflows and `browser_checks/guest_samples.py` passed in real
Chrome. Changed-file Ruff check/format passed. `./sigma test` passed every step,
including repository Ruff, formatting, Pyright, frontend typecheck, and build.
Local acceptance used temporary ports because standard ports were occupied;
GitHub Actions retains the workflow's standard ports. PR #246 is updated and
open for review, not merged. See the [Blue handoff](../messages/blue_guest_play_signin_r4r.md).

## PR #246 — latest-main integration and review refresh (2026-10-26)

Integrated current `main` at `6f6a910a64efd29268b5898b2e8f3e8c8791934a` in
merge commit `d527bef94f7bf0ddae562dce0b299de80e66082c`. The single conflict in
`frontend/src/main.tsx` was resolved by retaining the requested Privacy Policy
action while preserving main's new `/tos` route. Updated the T81 legal-page
browser check for that approved label. T92 Recent Projects, T200 Model
Availability, Guest samples/Play, and T81 legal-page browser checks passed in
real Chrome. Ruff check/format and `./sigma test` passed, including Pyright,
typecheck, and production build. PR #246 is updated and open for review, not
merged. See the [Blue R4R handoff](../messages/blue_guest_play_signin_r4r.md).

## PR #259 (T252) — Samples/Recent click tooltip (2026-10-27)

Changed the shared tooltip manager to display focus-triggered tooltips only for
`:focus-visible` elements. Mouse-driven focus during Samples/Recent switching no
longer displays tooltip text; delayed pointer hover and keyboard-visible focus
remain eligible. View selection, tab labels, and Home behavior are unchanged.

The focused `browser_checks/t252_samples_recent_tooltip.py` passed in real
Chrome with isolated guest auth/workspace fixtures. Clicking Recent and Samples
switches to the expected panel and leaves the tooltip absent after 600 ms;
hovering each tab still displays its expected tooltip. No page errors occurred.
`./sigma test` passed all scenarios, Ruff check/format, Pyright (0 diagnostics),
frontend typecheck, and production build. The build retains the existing >500 kB
chunk advisory; the Python suite emits the existing Starlette/httpx deprecation
and test-fixture resource warnings. No live sign-in, provider calls, or costs
occurred. See the [PR #259 / T252 handoff](../messages/t252_blue_samples_recent_tooltip.txt).

PR #259 follow-up: confirmed the failed T201 recovery CI job was caused by its
stale `Welcome to SIGMA` assertion after merged T88 / PR #251 removed that Guest
Home overlay. Updated `browser_checks/guest_samples.py` to assert the current
Projects/sign-in/Samples/Recent Home and explicitly assert the removed overlay
is absent, retaining the rest of the guest recovery workflow. The affected real
Chrome guest sample check and a fresh `./sigma test` both passed. All five
GitHub checks passed on implementation/test head
`5b574cf29ead711e20c32e86c5db2b73161d4444`: T200, T92, T201 recovery, Research
Outcome, and SIGMA verification. The handoff/status-only follow-up commit will
receive a fresh CI run before final R4R. See the
[PR #259 / T252 handoff](../messages/t252_blue_samples_recent_tooltip.txt).

## PR #257 T249 sample and T201 recovery CI remediation (2026-10-26)

Merged the latest `main` into `feature/local-mock-auth-walkthrough`, including
main's intentional removal of the pairwise-handshakes sample. Updated Recent
catalog coverage to compare discovered entries with the single-file sample
catalog. Replaced the removed ladder sample with Maximum Regions Formed by
Lines; the ladder checks its one active answer-free starter, distinct strategy
IDs, and continued preservation of the removed solution in the archived
strategy.

T201's fixture now uses a `.json` project and canonical inspected path. Its
browser acceptance reads saved session records from the project bundle. The
overflow message recommends creating a new strategy from saved findings, and
the browser recovery flow uses the visible New action. It still verifies that
blocked starts create no session, reserve no number, make no provider call,
and leave the source session unchanged before the fake-provider follow-up.

Local verification: `uv run --locked --no-sync python tests/recents.py`,
`uv run --locked --no-sync python tests/research_ladder.py`, and
`uv run python tests/research_sessions.py` passed. `browser_checks/t201_overflow.py`
passed in installed Google Chrome against the isolated local fake provider;
`browser_checks/t257_mock_auth.py` passed in installed Google Chrome. The
complete `./sigma test` passed, including Ruff, formatting, Pyright, frontend
typecheck, and production build. `git diff --check` passed. The build retains
its existing advisory about the JavaScript chunk over 500 kB; Python emitted
Starlette's existing `TestClient` deprecation warning. No live provider or OAuth
calls occurred; cost was $0. Final GitHub CI for the pushed head is pending.

The first GitHub T201 workflow on the remediation head passed its overflow
recovery and legal-page checks but failed in the chained Guest samples browser
check on stale Google-button, account-dialog, and Back-to-home expectations.
Updated that check for the current T88 pills, Privacy Close action, and SIGMA
logo navigation. Corrected the guest research “Sign in now” action to activate
the existing Google sign-in link; real-Chrome guest acceptance intercepts the
local login route and verifies no research or project mutations. The T201,
T257, guest-samples, legal-page, and full local verification suites pass after
these corrections. All six GitHub Actions workflows passed on implementation
head `57cdea354c752723a930ef45f3dddcd1c9982281`: SIGMA verification run
`40462919527` (#1037), T201 recovery `40462919422` (#197), T249 project
verification `40462919506` (#80), T200 availability `40462919443` (#212), T92
Recent Projects `40462919425` (#299), and Research Outcome `40462919416` (#368).
No live OAuth or provider calls, paid inference, or cloud changes occurred.

## Issue #279 — Invite me from the sign-in pill (2026-10-27)

Guests now see an **Invite me** pill beside the existing Google sign-in pill.
Opening it explains that Google verification is needed and links to the existing
`/api/cloud-auth/login?invite=1` flow. After sign-in, uninvited verified users
reach the existing invitation dialog, with their server-verified email and a
link to the proposed privacy notice. Submission reuses T81's invitation API,
recording, notifications, duplicate protection, and administrator review. While
sending, the action is disabled; an error remains recoverable; success shows
“Glad you're interested! Your request has been sent along to the right person!”
and removes the Invite me pill. The denied-identity endpoint reports only that
verified account's request status, so confirmation persists and the pill remains
hidden after reload. Authorized members/admins do not see the action. No
membership grant is made by requesting an invitation.

Verification: `uv run python tests/cloud_auth.py` passed (47 tests). The
real-Chrome check `uv run --with playwright python browser_checks/issue279_invite_me.py`
passed for desktop/mobile guest layout,
sign-in intent and explanation, verified invitation/privacy dialog, keyboard
submission, retry after a mocked failure, success confirmation, pill removal
after reload, and member visibility. The browser check uses deterministic API routes; live
Google OAuth and SMTP delivery were not exercised. `npm --prefix frontend run
build` passed (existing >500 kB chunk advisory). After formatting the new check,
`./sigma test` passed all scenarios, Ruff check/format, Pyright, frontend
typecheck, and production build. Existing Starlette/httpx deprecation and
resource warnings were emitted; no checks failed. No provider calls, live OAuth,
email, paid work, or production changes occurred. See
[issue #279 handoff](../messages/issue_279_blue_r4r.md).

PR #281 is open against `main` at `918aee4ecf9d4a54d89e5c2d7dd97009ebc401ad`,
mergeable, and not merged. Its pushed implementation and R4R handoff are on
`blue/issue-279-invite-me`.

### Issue #279 human-requested allowance-zero correction

The guest pill now reads **Invite me!**. When the current hosted allowance
reports `remaining_usd <= 0`, signed-in users see **Reload me!** in the same
header-actions slot used by **Admin**. The action reloads the page; the existing
budget refresh updates the zero-allowance state. The extended real-Chrome check
passed at desktop and mobile widths, including positive-to-zero transition,
slot placement, page reload, and mobile overflow. Frontend typecheck and a fresh
`./sigma test` passed. This correction is part of PR #281; no live or paid
provider work was run.

### Issue #280 follow-up — sponsor welcome and pill state

The sponsored welcome appears on each fresh page entry for an authenticated
sponsorship-eligible account, and does not reopen on a browser reload. It
starts with “Welcome to SIGMA.” followed by the randomly selected curiosity
sentence as normal dialog text. The browser check verifies a new page entry
shows the greeting again while a reload does not. The sponsored pill now keeps
cloud funding context in every header render path. Clicking a connected local
sponsored pill disconnects the local ChatGPT connection; sponsored mode is
rediscovered on reload. Server-side grant eligibility,
provider admission and spending limits remain enforced. The reload action now
records an administrator-reviewed reload request rather than refreshing the
page. During a running research session, the outcome label now shows a summary
of the current action and focus, refreshed as session state updates and capped
at 50 words. It falls back to “Pending · provisional” when no status text is
available. Reopening an active project through its Home Recent project title
expands Sessions and scrolls to the running session.

Verification: `uv run --with playwright python
browser_checks/hosted_sponsored_connection.py` passed in real Chrome with
deterministic API fixtures, including sponsor welcome entry/reload behavior,
normal text styling, sponsored allowance text/hover/focus/tap, and connection
flow. `tests/cloud_auth.py` passes (54 tests), including local signed-in grant
allowance preview, mock allowance, server-rejected personal switch, and restored
sponsored mode after reload. `npm --prefix frontend run typecheck` and
Pyright pass. The A17 browser script currently stops at an obsolete export
dialog assertion before its new running-session checks; it is not recorded as
passing. `browser_checks/issue279_invite_me.py` passed desktop/mobile
invitation and reload-request cases. The default local checkout Cloud Auth
configuration is disabled. `--sponsored` applies only to an eligible, actually
signed-in local Google account; it does not enable mock auth. The pill reads
that account's balance from its local sponsored-spend ledger. Sponsored model
calls use SIGMA's designated ChatGPT account, pinned to
`zetacontinuation@gmail.com`, rather than the member's ChatGPT session. The
ledger reserves per-account cost before provider dispatch. Only explicit
`--mock-auth` enables mock identities, controls, and the simulated `$25`
allowance. Restart SIGMA after upgrading to clear a previously running process
launched with the old flag behavior. No production config or default-off hosted
flag was changed.

The local `./sigma start --sponsored` option is loopback-only and applies to an
eligible Google account actually signed in to the local app. It does not enable
mock auth or select a simulated member. The pill reads that account's
balance from its local sponsored ledger; the tooltip uses the custom SIGMA
tooltip without a duplicate portal tooltip. In this mode inference uses the
designated sponsor account `zetacontinuation@gmail.com`, and spend is reserved
against the member's allowance. At zero, the sponsored control changes to
**Reload me!** and records an administrator-reviewed reload request. Only
explicit `--mock-auth` enables mock identities, scenario controls, and the
simulated `$25` member allowance. The server rejects personal-mode changes while
the local force flag is active. This option does not set
`SIGMA_CLOUD_FORCE_SPONSORED_MODE`, which remains default-off.

Local play failure follow-up: the local sponsored provider now defaults to the
designated ChatGPT sponsor even when `SIGMA_CLOUD_INFERENCE_PROVIDER` is unset.
Connection checks, credential validation, and spend-ledger job records use the
same provider selection. This change alone did not repair a previously saved
personal provider choice, so it could still surface the generic expired
ChatGPT error. `./sigma test` passed after this change, and
`browser_checks/hosted_sponsored_connection.py` passed in real Chrome. The
local UI was restarted with `./sigma start --nav`; no live model generation was
used for verification.

Request error toasts are capped at five visible items. Adding a sixth removes
the oldest toast and clears its timers before inserting the new item.

The portfolio research failure summary now deduplicates repeated branch error
messages, so parallel responses over the existing 1 MB transport safety bound
report the reason once. The response-size safety bound itself is unchanged.

Local Play expiry correction: the reported account is
`nontrivialzeero@gmail.com`. Its local state was funding-eligible but selected
`personal`, while the pill still displayed sponsored text. The designated
sponsor record was present but had no usable access or refresh token. Local
connection checks now restore sponsored mode when a personal ChatGPT session
is disconnected or requires reauthorization. The pill reflects the selected
mode. Clicking a sponsored pill attempts a personal ChatGPT connection and
switches mode only after success. Sponsor selection now finds the designated
account even if another ChatGPT account is active in the local store. A local
Google administrator can renew the existing sponsor account via **Admin
Settings → Reconnect sponsor ChatGPT**. Provider calls remain blocked until
that sign-in completes. No credential values or live model calls were used in
the diagnosis or verification.
The corrected tree passed `./sigma test` (including Ruff, Pyright and the
frontend production build) and the real-Chrome sponsored connection check.

Local sponsor credential follow-up: the private store was inspected through
metadata only and had two registrations for the designated sponsor, neither
with an access or refresh token. Rerunning SIGMA cannot restore a missing
ChatGPT credential; the Google administrator must complete **Admin Settings →
Reconnect sponsor ChatGPT** as `zetacontinuation@gmail.com`. A local personal
connection now refuses to use the designated sponsor registration, and the
ordinary sign-in and disconnect endpoints cannot renew or revoke it. Sponsored
inference chooses the designated account even if a personal/API-key billing
choice changes the shared store's active mode; duplicate registrations prefer
one with usable tokens. This preserves the sponsored ledger and avoids an
unmetered personal path after admin renewal. Focused `tests/cloud_auth.py`
(56 tests) and `tests/cloud_sponsor.py` (11 tests) passed. The real-Chrome
`browser_checks/hosted_sponsored_connection.py` passed, and `./sigma test`
passed all steps after formatting the new test. No live ChatGPT sign-in or
provider inference was performed; Play after admin renewal remains to be
checked by the human.

Sponsored-pill tooltip wording follow-up: the local, switchable sponsored
control now begins its custom hover/focus/tap explanation with “Click to switch
to your own ChatGPT account.” Remaining allowance and connection details stay
in the same tooltip. Forced sponsored mode and hosted controls do not offer
that instruction because their pill cannot switch to a personal account.
The real-Chrome sponsored connection check, frontend typecheck, and `./sigma
test` passed with the new wording. No provider call was made. A metadata-only
recheck after the reported Play error still found no access or refresh token
for either designated sponsor registration, so live Play remains blocked on
the administrator's interactive renewal.

Member-facing sponsor outage correction: research and connection checks now
say “SIGMA-sponsored ChatGPT is temporarily unavailable. Please try again
later. Saved research is unchanged.” They do not direct members to perform an
administrator action. The backend terminal emits token-free, rate-limited
`sponsor_connection status=...` diagnostics and `sponsor_oauth status=...`
renewal events, so the operator can distinguish
missing registration, absent credentials, failed validation, and completed
OAuth without exposing tokens or identities. The current local store still
has no sponsor access or refresh token. This change improves diagnosis and
member UX; it does not provision a sponsor session or claim live Play success.
`tests/cloud_auth.py` (56 tests), `tests/cloud_sponsor.py` (11 tests), the
real-Chrome sponsored connection check, and `./sigma test` passed. No live
OAuth, inference, or paid provider call was made.

Local sponsor diagnostics are now also written to the checkout-root
`sponsor-diagnostics.log` (owned 0600, ignored by Git, capped at 64 KiB).
Only fixed event and status codes with timestamps are stored; credentials,
account identities, provider responses, and request payloads are excluded.
Writes refuse symlinks and unsafe files and cannot block research. The
operator or developer can inspect the same file with `tail -n 20
sponsor-diagnostics.log` after a failed Play or renewal attempt. Hosted
deployments continue to use their service logs.
An offline call through the real `sponsor_session()` path wrote a 71-byte
0600 file in this checkout and reported `credential_missing` for two
designated registrations. No token refresh or model call was attempted.
`tests/cloud_sponsor.py` (12 tests), `tests/cloud_auth.py` (56 tests), the
real-Chrome sponsored connection check, and `./sigma test` passed.

The launcher now passes `--sponsored` and `--mock-auth` independently to the
local UI. `--sponsored` alone forces the eligible signed-in account's sponsor
state without enabling mock identities or controls; combining both flags still
enables the explicit mock walkthrough. A CLI regression checks both invocations.
`tests/tooling.py`, the real-Chrome sponsored connection check, and `./sigma
test` passed after this correction. The older `browser_checks/t257_mock_auth.py`
stops at a stale `.project-google-signin` locator now matching both Sign out
and invitation sign-in controls; it was not used as evidence of a pass.

## Local sponsored service credential route (2026-10-27)

The remaining local Play blocker is an absent sponsor ChatGPT credential: the
two registrations for the designated sponsor have neither access nor refresh
tokens. Local sponsored inference now keeps ChatGPT as its default but accepts
an explicit `SIGMA_CLOUD_INFERENCE_PROVIDER=api_key` choice backed only by
`SIGMA_CLOUD_OPENAI_API_KEY` or its `_FILE` source. It does not borrow a
member's ChatGPT credential or the checkout's `OPENAI_API_KEY`. Missing or
invalid service configuration fails closed. The local sponsored ledger still
reserves each eligible member's allowance before provider calls; the hosted
provider default and production forced-sponsorship setting are unchanged.
The launcher excludes both dedicated secret forms from the frontend process.
Configuration and rollback are in `docs/GETTING_STARTED.md`. The service key
has not been provisioned here; live Play remains unverified and requires an
operator-approved, funded key or an interactive sponsor ChatGPT renewal.
The reported `$0.01` member balance may be insufficient for the first
model-specific call reservation; no spending limit was relaxed.

Verification: the focused local provider and launcher regressions passed; the
real-Chrome `browser_checks/hosted_sponsored_connection.py` passed with
deterministic mocked API responses. `./sigma test` passed all steps, including
Ruff, Pyright, frontend typecheck, and production build. No paid request or
production change was made.

Follow-up: the active local grant for `nontrivialzeero@gmail.com` was changed
through SIGMA's allowance service from `$0.01` to `$0.25`; the admin snapshot
read back `$0.25` effective and `$0.25` remaining, with zero held or estimated
usage. The account remains an eligible member in sponsored mode. The private
sponsor store still has two registrations with no access or refresh token, and
no dedicated sponsored API key is configured. Local sponsored service-key
connection status no longer reads unrelated ChatGPT account preferences. A
new isolated local Google-member API regression starts and completes a
two-call research session at a `$0.25` grant using a fake sponsored key and
fake provider outputs, with the member's saved sponsored choice and the local
force flag off. It asserts the dedicated key path and allowance ledger.
This establishes the local Play routing without making a paid provider call;
live Play remains unverified until an approved credential is provisioned.
An offline call to the current signed-in member's server-side auth context
returned `mode=chatgpt`, `status=reauth_required`, and no credential; the
private diagnostic recorded `sponsor_connection status=credential_missing`.
The running local API process predates the service-key commit and will need a
restart when a sponsored credential is configured. No user retry was requested.
The focused local Play regression passed; the real-Chrome sponsored connection
check passed with mocked API responses; `./sigma test` passed all steps,
including Ruff, Pyright, frontend typecheck, and production build.

Sponsor-account and member-reconnect follow-up: OpenAI's metadata endpoint
associates the checkout's `OPENAI_API_KEY` with API user
`zetacontinuation@gmail.com` and the API organization named `Personal`; the key
can list `gpt-6.1-sol`. No inference request was sent. This is API billing,
separate from the ChatGPT subscription, and the key was not copied into the
sponsored setting. The account's ChatGPT browser session was switched to the
designated sponsor identity, but SIGMA still had no saved sponsor token.

To remove the SIGMA-admin dependency for that renewal, authenticated, eligible
local members can now start the existing sponsor OAuth flow by clicking the
sponsored pill when its ChatGPT credential needs reauthorization. The route is
local-only, rejects mock and ineligible users, and remains bound to the saved
designated sponsor registration and subject. It grants no admin settings
access. The normal connected-pill action still starts a personal ChatGPT
connection. Real-Chrome acceptance covers the member flow, and the focused
auth regression verifies eligible access, ineligible denial, and admin access.
`./sigma test` passed all steps. The running app was restarted on the updated
branch.

Pill-click correction: the allowance amount is a nested button that stops
click propagation so it can show its tooltip. In sponsor `reauth_required`
state, clicking that amount now starts the same sponsor reconnect action as
clicking the pill label. The Chrome regression uses the amount button, verifies
the `/api/ai/sponsor-auth/begin` request and checks that no extra message appears
under the pill. The real-Chrome check passed, and `./sigma test` passed all
steps on this fix. No paid request is sent.

Live connection verification: the member completed sponsor OAuth as
`zetacontinuation@gmail.com`. The diagnostic log recorded `sponsor_oauth
status=started` then `connected`. Metadata confirms an access token, refresh
token, and required plan scopes on the designated account; values were not
printed. The member's fresh server auth context is `chatgpt/connected`, model
catalog verification returned `connected`, and `gpt-6.1-sol` is available.
The `$0.25` allowance remains fully available with `$0` estimated and held
usage. No inference call has been made; the user was told to click Play.

## Local sponsored project-call setting (2026-10-27)

The sponsored Play preflight reported that five enabled strategies required ten
calls while the project allowed six. The cause was a policy mix-up: local
sponsored users use the durable sponsored-spend ledger, and the project settings
service treated that as hosted billing and silently applied the hosted
six-call cap. The backend admission gate also applied that hosted cap, so
changing Maximum agent calls in the local dialog appeared to have no effect.

Local sponsored limits now retain the saved project call count up to 30. The
hosted six-call cap remains unchanged. Local sponsored sessions remain capped
at 15 minutes and $0.25 per session; per-account allowance reservation and
spend checks are unchanged. The settings dialog now describes the local cap
separately from hosted limits. `tests/cloud_auth.py` exercises an authenticated
local sponsored member saving, re-reading, and starting a fake-provider session
with a 12-call limit. `tests/cloud_research.py` covers both local and hosted
call ceilings. `browser_checks/local_sponsored_limits.py` uses real Chrome and
a deterministic API fixture to save 12 in Project Settings and verify the
value after reload. The full `./sigma test` passed, including Ruff, formatting,
Pyright, frontend typecheck, and production build. The local SIGMA service was
restarted from the corrected tree, and the authenticated browser reopened the
active Xenopus project. The saved call limit is 12. No live provider call or
production configuration change was made.
## Sponsored Play failure investigation and guest welcome (2026-10-27)

The local account record for the tested member is eligible, sponsored, and
marked connected. The existing `sponsor-diagnostics.log` ends at OAuth success
and has no inference result, so the failure has not yet been localized. The
reported oversized panel is SIGMA's request-error toast: the browser surfaces
long API error details without identifying their source. Toasts now summarize
oversized server errors, cap message text at 600 characters, and constrain the
stack to 70% of viewport height.

For the next run, local diagnostics record token-free `sponsor_play`,
endpoint-specific `sponsor_*_api`, and `sponsor_inference` outcome codes. They
exclude request/response bodies, identities, and credentials. Read the log with
`tail -n 30 sponsor-diagnostics.log` in the checkout. The live Play cause
remains **UNVERIFIED** until a sponsored run reaches this instrumented backend;
no live or paid provider call was made during this investigation. Guest first
entry now has a one-time, dismissible welcome alongside the sponsored welcome.


## Local sponsored Play preflight diagnosis (2026-10-27)

The shared private diagnostics log recorded `sponsor_play status=post_400_large`
for the user's 17:11 local attempt. The response text identifies the exact cause:
research admission stopped before dispatch because the strategy's prior-session
unresolved-obligation snapshot exceeded its 32 KB bound. No sponsored provider
call was made, so the ChatGPT sponsor session was not involved in this failure.

The frozen snapshot now compacts repeated provenance pointers to the first and
latest references only when that metadata is what exceeds the byte bound. It
retains each obligation's full text, scope, identity, and durable source records,
and reports the number of compacted references in the context manifest. If the
obligations themselves still cannot fit, admission remains fail-closed with a
short message and no saved research changes. The Play failure path no longer
creates a duplicate toast. Guest intro copy now presents guest exploration,
Google sign-in for saving, and invitation requests as separate choices. Guest copy
now clarifies that guests cannot run or save projects and that the administrator
decides whether to include sponsorship when granting an invitation.

Regression coverage in `tests/research_sessions.py` passed, including 15 obligations
with 32 source artifacts each and the retained over-count rejection. The hosted
Chrome invitation/welcome check passed. `./sigma test` passed all scenarios,
Ruff, formatting, Pyright, frontend typecheck, and production build. A post-change
sponsored Play attempt remains pending; no live or paid provider request was run
during verification.

### Follow-up: context compaction did not clear the user's admission error

The user's post-change Play attempt still returned HTTP 400: 15 obligations for
“Establish the known-mechanism frontier” and 14 for “Find a novel temporal
coupling, not another marker” remained beyond the context bound. This disproves
the assumption that repeated provenance pointers were the only oversized fields.
The prior synthetic test covered repeated references but not the user's full
assumption/rationale payload or aggregate selected-strategy shape; it was not
sufficient acceptance evidence.

The next diagnostic records only aggregate selected bytes, omitted count, and
maximum UTF-8/JSON byte sizes for obligation text, scope assumptions, rationale,
and provenance. It emits no project text, IDs, email, or credentials. The cap
remains fail-closed until those measurements identify a safe compaction or budget
change. The latest local retry was read from the shared diagnostic log and is
documented in `docs/SPONSORED_PLAY_INVESTIGATION.md`: 12 obligations omitted,
31,118 selected JSON bytes, with max text/scope/rationale/provenance fields of
156/414/0/416 bytes. This points to aggregate history volume, not a single
oversized field. The request was rejected before provider dispatch. Fixture
tests do not reproduce the user's saved obligation payload or prove real sponsor
inference.

Guest header cleanup now hides the unusable ChatGPT connection pill for
unauthenticated cloud guests on Home and project pages. Real Chrome guest/sample
and hosted sponsored-connection checks passed, including six visible
project-header actions. Full `./sigma test` passed on the current changes (284
Python files formatted, Pyright clean, frontend typecheck and production build
passed). This UI change does not fix or validate sponsored Play. The next
deliberate sponsored Play attempt is for safe payload measurement; if admission
passes, it may dispatch a real sponsor inference and consume allowance.

### Sponsored Play follow-up and home-page persistence (2026-10-27)

The 6:02 PM Play failure used a stale backend: PID 79836 began at 5:56:42 PM,
while the 64 KB context-cap source edit was written at 6:04:31 PM. Thus this
retry did not test the change. A read-only reconstruction of the saved ledger
retained all 39 unresolved obligations in 44.7–58.6 KB role contexts, below the
256 KB context ceiling. The separate conservative cost-reserve formula appears
capable of being the next gate ($0.29–$0.35 estimated versus the $0.25 session
cap for the current saved model/settings); this has not been observed live and
is not being weakened. The user authorized one more Play trial, then escalation.
The trial may dispatch a provider call and consume sponsored allowance.

Home Catalog expansion for Samples and Recent category groups now persists in
local storage across project navigation. Project Settings also restores the
last selected tab. Settings and help text now allow 120 local calls and 20,000
output tokens while retaining the 30-call default, 12,000-token default, hosted
six-call cap, sponsored $0.25 cap, and 15-minute sponsored duration cap.

The sponsored-obligation regression now creates 39 unresolved obligations across
three strategies with 32 source references apiece. It asserts the snapshot is
larger than the previous 32 KB cap, keeps every obligation, and remains within
64 KB. The focused research-session scenarios and the full `./sigma test` both
passed after this regression was added.

### Local sponsor admin connection and allowance reload (2026-10-27)

The configured local bootstrap administrator is sponsorship-eligible while
retaining the admin role. The normal connection pill can select sponsored mode
and renew the designated ChatGPT session; Admin Settings no longer exposes a
separate sponsor-reconnect control. The authorized-users `New`, `Reload`, and
`Remove` actions share the established underlined admin action style.

An admin Reload action is shown only for a member email account with spend in
its current allowance window. Reload begins a new per-user allowance window at
the configured effective amount while preserving historical call records and
the global spend ledger (including unresolved provider charges). The action is
audited; a browser refresh confirms it disappears after reload until new spend
is recorded. Reload uses `POST /api/cloud-auth/admin/grants/reload/{email}`.

Verified with 60 cloud-auth tests, cloud-research ledger tests, real-Chrome
`browser_checks/hosted_sponsored_connection.py`, and full `./sigma test` (all
steps passed, including Ruff, Pyright, frontend typecheck, and production build).
No live provider call or production setting was changed.

### Sponsored allowance config and sign-in return (2026-10-27)

The latest user Play attempt passed prior-obligation admission (`o0` omitted),
then failed job preparation because code required a configured default
per-user allowance even for an account with an explicit grant. Preparation now
checks the account's effective allowance: configured account/domain amounts work
without a fallback default; accounts using fallback still require a valid
configured default. The $15 per-user ceiling, global ceiling and $0.25 session
cap remain enforced.

Google sign-in launched from guest Play now carries a validated project path in
the short-lived server OAuth flow. Successful authorized sign-in returns to that
project; denied authorization continues through the existing invitation flow.
The welcome dialog also dismisses when its backdrop is clicked. OAuth return
paths are limited to the local `/project?path=...` route to prevent open
redirects. Targeted cloud/auth tests, real Chrome guest and local-sponsored
checks, and full `./sigma test` passed. No live provider call or production
configuration change was made. The conservative reserve may still reject a call
under the unchanged $0.25 session cap; that remains to be observed and handled
without weakening spend accounting.

## Complete project export and import contract (2026-10-28)

The standard `GET /api/projects/export` endpoint and the workspace's Project
file action now return one portable JSON bundle containing every project file,
including saved research history, evidence and artifacts. `POST
/api/projects/import` restores that bundle into the current workspace without
replacing existing projects. The former structured audit response remains at
`GET /api/projects/audit`; readable reports continue to use
`/api/projects/export/report`. `/api/projects/download` remains a compatibility
alias for the complete bundle. The UI labels the project file as complete and
importable and explains what it contains.

Focused checks passed: `tests/project_bundle.py`,
`tests/project_creation.py`, `tests/project_settings.py`, and
`npm run typecheck` in `frontend/`. `git diff --check` passed. The full
`./sigma test` run was stopped at the user's request while in
`tests/research_sessions.py`; it is incomplete. No real-browser check was run for
the export dialog change. Existing untracked project exports were left untouched.

## Identity tooltip and configurable hosted call limit copy (2026-10-28)

The authenticated Google sign-out pill now exposes a hover/focus tooltip with
the signed-in email. Hosted Project Settings → Limits shows the current
configured call count and distinguishes it from the hosted maximum of six calls.
`git diff --check` passed. No automated or real-browser checks were run for this
copy and tooltip update.

## Home Saved tab label (2026-10-28)

The Home catalog tab now reads “Saved,” and its tooltip describes saved
projects. Existing recent-project storage and navigation behavior are unchanged.
`git diff --check` passed; no browser or automated checks were run.

## Local Saved tab sharing disclosure (2026-10-28)

The Saved tab tooltip now clarifies that local mode uses one shared project
list. Hosted guests retain the sign-in tooltip, and hosted signed-in accounts
retain the regular saved-project tooltip. `git diff --check` passed; no browser
or automated checks were run.

## Samples copy tooltip (2026-10-28)

The Samples tab tooltip reads “Selecting a sample copies into a new project.”
`git diff --check` passed; no browser or automated checks were run.

## About dialog spacing (2026-10-28)

Removed the “Strategies set direction…” sentence from the About dialog. The
space between the intro and disclosures is now just the intro's 8px bottom gap.
`git diff --check` passed; no browser or automated checks were run.

## Project file export label (2026-10-28)

The export option now reads “Project file”; its hover text says it can be
imported into a different SIGMA account. `git diff --check` passed; no browser
or automated checks were run.

## Readable project export and viewport-safe remove tooltip (2026-10-28)

Portable project exports now use bundle version 2: JSON members are embedded
as JSON, UTF-8 members as text, and only binary or invalid-UTF-8 content is
Base64 encoded. Import still accepts version 1 and stores projects in the
existing internal format. Operational `.lock` files are omitted because they
are regenerated locally. The Saved Projects Remove tooltip now uses the
viewport-positioned tooltip.

Focused checks passed: project bundle, project creation/import API, project
reports, and Ruff on the changed Python and browser-check files. The real
browser recents check and full `./sigma test` suite were not run.

The Saved Projects removal confirmation flips above its Remove row near the
bottom of the viewport, staying adjacent to its trigger. Confirm and Cancel
retain the underlined text-action style and use the standard yellow action
color. The browser check asserts the tooltip and
confirmation stay within the viewport and the confirmation stays close to its
trigger. The frontend TypeScript and production build passed; the browser check
remains unrun because the local API server was unavailable.

## Forget unavailable Saved Projects by path (2026-10-28)

The Remove action sends the saved path as a query parameter alongside the
ID-only JSON body, which remains compatible with older running servers. The
forget endpoint removes a matching entry by either stable ID or saved path, so
identity drift in the project document does not block cleanup. The
recents scenario verifies removal when the project document ID no longer
matches its saved index identity. Focused recents tests and Ruff passed.

## Sponsored ChatGPT pill spacing (2026-10-28)

The Sponsored ChatGPT pill now matches the Sign out indicator-to-label gap and
tightens the label-to-allowance gap. Frontend build passed.

Request toast Dismiss actions use the same yellow text-action color as other
actions in the app.

## Project limits copy and field sizing (2026-10-28)

Removed fixed hosted/local call, duration, and spending amounts from the
Project Settings → Limits guidance. Shortened Maximum concurrent sessions help
to one sentence. Limit inputs now share a compact width that fits eight-digit
values. The local sponsored-limits browser assertion follows the revised copy.
The duration unit selector is narrower and has added right padding for its
chevron.

## Project settings Research tab sizing (2026-10-28)

Narrowed the Difficulty and Thinking level controls in the edit dialog and
shortened the Research tab introduction.

The Project Settings dialog title now reads “Project Settings.” Research type
and Model controls share a 240px width, the Research type icon-to-label gap and
space above the control are smaller, and the Research introduction's bottom
margin is reduced. Thinking level and Model captions are shorter. The project
header Thinking pill is left-aligned, and the Model pill no longer repeats its
label.

## Issue #289 — Project configured sponsored limits (2026-10-28)

Sponsored sessions now use the saved Project Settings call, round, and maximum
estimated cost limits rather than overriding them with six calls or $0.25.
Hosted and local sponsored sessions retain the service 15-minute cap and
account/global allowance checks. Unknown provider attempts continue to retain
their reservation. A cost-limited portfolio now reports the affected cycle,
call count, branch reason, and undispatched next role while retaining its
partial cycle in the outcome. Starting sponsored work without a configured
maximum estimated cost returns an actionable Project Settings message.

Import title collisions now preserve the exported project by assigning a new
versioned title (for example, “v1” becomes “v2”); non-versioned collisions use
an imported suffix. Existing imported bundle formats remain supported.

Focused verification passed: `tests/cloud_research.py`,
`tests/cloud_research_api.py`, `tests/cloud_research_sponsored_api.py`,
`tests/research_sessions.py`, `tests/project_creation.py`, and
`npm --prefix frontend run build`; Ruff formatting and `git diff --check` also
passed. The full `./sigma test` was not run, as requested. No real-browser
check was run. Hosted personal ChatGPT authorization remains disabled by the
existing hosted integration, so hosted personal-account switching is blocked
and unchanged; no authorization requirement was bypassed. No live or paid
provider calls were made.

Follow-up from local Session 6: its first sponsored provider call received an
explicit ChatGPT plan/app usage-limit rejection. SIGMA had retained the full
write-ahead reservation as unknown, then attempted the remaining strategies,
which were reported as cumulative sponsored allowance failures. Known HTTP 429
or explicit ChatGPT usage-limit responses now settle as zero-usage rejected
attempts, release the held spend/token reservation, stop remaining strategy
dispatch, and report the provider limit without switching billing sources.
The session remove confirmation also no longer says that other strategies and
sessions will remain. Regression coverage was added; verification is deferred
for local testing. This cannot clear the designated ChatGPT account's own usage
cap, so a new session can proceed only after that provider limit permits use.

## Sponsored account initial connection (2026-10-28)

Eligible accounts now start with SIGMA sponsorship selected until the user
explicitly chooses a connection. The selection is persisted so a personal
choice remains personal on refresh. Added a migration-safe explicit-choice
field and updated auth regression cases. Personal mode no longer silently
changes back to sponsorship when its ChatGPT connection is disconnected or
needs reauthorization.

The session cost cap is visible in hosted Project Settings and local sponsored
settings. It is optional; without a project cap, sponsored sessions remain
subject to ChatGPT and SIGMA allowance limits. The confirmation says “no
session cost cap” when no project cap is configured.

Verification was deferred for local user testing. A `tests/cloud_auth.py` run
started just before that request and failed two scenarios that assumed new
eligible accounts began in personal mode; those cases were updated but not
rerun. After local testing was requested in parallel with automated
verification, `tests/cloud_auth.py` passed all 60 tests. Frontend typecheck,
Ruff check/format, and `git diff --check` passed before the optional-cap
follow-up. Verification of that follow-up is deferred until after local testing.
The real-browser check did not complete; it stopped at an assertion in the
local connection-switching scenario.

## Lean project action visibility (2026-10-28)

The disabled Lean proof action is now visible in the project button bar for all
research types, matching the consistently visible TeX and export actions. No
tests were run; this change is committed for local browser verification.

## Sponsored unlimited-cost session reservation (2026-10-28)

Diagnosed the tadpole session ending with 0/30 calls. Its five sponsored
strategy branches were all rejected before provider dispatch because the
optional project cost cap was unset and no per-call estimate was passed to the
global sponsored allowance ledger. Sponsored calls now reserve their reviewed
model estimate against SIGMA's global allowance even when no project cap is
configured. Reservation failures are surfaced with their actual reason instead
of the generic shared-call-budget message. Sponsored portfolio calls are
serialized within a session so concurrent sibling reservations do not consume
the available allowance while a call is still in flight.

`tests/research_sessions.py` and scoped Ruff check/format passed at the final
implementation SHA. `./sigma test` was run and stopped with unrelated failures
in `tests/cloud_personal.py` (the
fixture expected an unavailable personal account) and a pre-existing import
ordering issue in `src/sigma/api.py`; Pyright and frontend typecheck passed, and
the frontend build was skipped after those failures. No provider calls were
made.

## PR #293 stabilization (2026-10-28)

Updated browser acceptance checks for the current Saved tab label, Project
Settings title, optional Unlimited sponsored session cost, and current Home
pill spacing. T92 now reads the created sample's versioned title instead of
assuming `v1`; Home status coverage explicitly expands saved project groups.
This fixes stale T92 and T201 browser expectations without changing product
behavior.

`./sigma test` passed all steps locally (Python 3.14.7), including streamed
provider diagnostics and portfolio finalization. Real-browser checks passed
for hosted sponsored connection, model availability, local sponsored limits,
T92 Saved running status, T201 guest sample workflow, and Home Saved running
status. Ruff check/format and `git diff --check` passed. No live provider calls
were made. GitHub Actions all passed at implementation commit
`f01d4417f1ae64123d9b20d2758b29224ca709c9`: SIGMA verification, T200, T201,
T249, T92, and Research Outcome.

## T313 Gray UI quality pass (2026-10-28)

On `gray/ui-quality-pass`, based on `main` / `origin/main` at
`2cf878a3290e697b408ebdb5d58871690e2c030b`, the narrow Home view now suppresses
the oversized slogan and dims the established background artwork so sample
content remains readable. The ChatGPT connected tooltip no longer includes a
provider account label; visible connected/disconnected/sponsored states and
click behavior remain intact. Main already contained the Sponsorship Allowance
alignment correction from PR #232; this pass added browser regression coverage
for `$2`, `$15`, and Unlimited at desktop and narrow widths.

Real Chrome checks passed for allowance alignment (1440/390), connection states
and Home overflow (1440/390/320), the narrow New Project dialog (390), and
Project About disclosure/focus behavior (1440/390). Screenshots and audit
limits are in `docs/evaluations/t313/`. `npm run typecheck`, the `./sigma test`
suite (all steps, including frontend build), Ruff format/check, Pyright, and
`git diff --check` passed. The end-to-end A17 browser walk stopped at a fixture
HTTP 403 on account changes; those screens/actions overlap Green's active
authentication ownership and were not changed. Session playback/progress,
results, and research-output browser states therefore remain unverified.
No paid provider calls were made. R4R is open as
[PR #316](https://github.com/bkramerext/sigma/pull/316); no self-merge.
