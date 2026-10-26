# A7 browser checks

T46 About-dialog acceptance uses a local UI and the deterministic provider
fixture. Start them in separate terminals:

```sh
uv run uvicorn provider_fixture:app --app-dir browser_checks --host 127.0.0.1 --port 8026
npm --prefix frontend run dev -- --port 5193 --strictPort
```

Then run the real-Chrome check:

```sh
uv run --with playwright python browser_checks/about.py
```

The check covers Home and Project at 1440px and 390px, keyboard dismissal,
focus restoration, state preservation, and no request on opening About. It saves
screenshots to `/tmp/sigma-t46-about-*.png`. Set `SIGMA_BROWSER_FIXTURE_URL` or
`SIGMA_BROWSER_BASE_URL` to use different local ports.

These checks create temporary projects and use an explicitly identified HTTP
provider fixture. They never call OpenAI or use real credentials. The fixture is
not loaded by `sigma ui` and never belongs in a production launch. Test context
and model names explicitly say TEST-FIXTURE.

Start the normal UI with `./sigma ui`, then in another terminal:

```sh
uv run uvicorn provider_fixture:app --app-dir browser_checks --host 127.0.0.1 --port 8001
```

Run:

```sh
uv run --with playwright python browser_checks/strategies.py
uv run python browser_checks/http_cancel.py
```

The first check uses installed Chrome at its usual macOS path; set
`SIGMA_BROWSER_EXECUTABLE` for a different installed Chromium executable. It
intercepts API traffic only in its own browser and forwards it to the isolated
fixture server. Screenshots are written under `/tmp/sigma-a7-*.png`.

Touch uses actual Chrome CDP touch events, not fabricated DOM drag events. This
is browser emulation, not a claim of physical phone testing. Desktop mouse,
keyboard, stage/manual CRUD and editable AI-draft acceptance are also exercised.
The second check uses actual HTTP disconnection to verify backend cancellation
and slot release, independently of Playwright's forwarding request lifecycle.
Stop the fixture server after testing; leave the ordinary UI running as desired.

A8 shared project form and connection-status checks use the same fixture:

```sh
uv run --with playwright python browser_checks/settings.py
```

The fixture uses its own temporary managed-project root. The settings check covers
Create/Edit field order, Sol/High, mode/model/effort changes, no-op/cancel/focus,
failed-save retry, synchronous duplicate submits/busy handling, stale editors,
offline model retention/metadata save, explicit unsupported-effort correction,
connection checking/green/auth/permission/rate/offline/stale labels and mobile
screens. The fixture's authenticated `/v1/models` response includes an unreviewed
ID deliberately; it must never become a dropdown option. This is a controlled
transport test, not verification of real API credentials, credits or billing.

## A8.2 ChatGPT-plan sign-in

Stop the API-key fixture before starting the separate OAuth fixture on port 8001:

```sh
uv run uvicorn chatgpt_fixture:app --app-dir browser_checks --host 127.0.0.1 --port 8001
uv run --with playwright python browser_checks/chatgpt.py
```

The normal UI stays on 5173. Only the test browser forwards API requests to the
fixture. The fixture creates private temporary app/project storage, validates
real PKCE/code exchange and signed generated RSA ID tokens, and supplies bounded
SSE. The browser substitutes the trusted authorization redirect with a simulated
provider callback; it never contacts a live OAuth account. Tests cover manual
work while disconnected, cancelled/declined auth with seed retained, one resumed
generation, explicit human save, welcome once, accounts, billing choices, limits,
expiry/offline/permission states, keyboard focus and 1280/1440/390/320px screens.
Screenshots: `/tmp/sigma-a82-*.png`. These are fixtures, not live entitlement or
plan-capacity verification. The API-key regression fixture explicitly selects
its dummy key mode during fixture startup; production never does that implicitly.

### A8.2.1 connection health refresh

With the normal UI running on port 5173, run
`uv run --with playwright python browser_checks/connection_refresh.py`.
This focused Chrome check uses a controlled clock and mocked browser fetches to
verify the shared 48-second refresh schedule for a 60-second TTL, stable status
during background and manual requests, hidden-tab pause/resume, transient failure
backoff and Retry, and one-time welcome behavior. It makes no provider calls.

## A11 Home catalog and recents

Start a fresh `provider_fixture:app` as above, then run
`uv run --with playwright python browser_checks/recents.py`.
This check expects a fresh disposable fixture state. It covers the Samples and
Recent tabs, Samples as the default selection, keyboard tab switching, direct
sample opens without a dialog, independent working-copy creation, inclusion of
that copy in Recents, source-file immutability, and 1280x720, 390x844 and
320x700 layouts. Captures are `/tmp/sigma-samples-*.png`.
`settings.py` remains the shared-form persistence/focus regression.

For live session activity in the Home Recent metadata, start a fresh
`provider_fixture:app` on port 8001 and the normal UI on port 5173, then run
`uv run --with playwright python browser_checks/home_running_status.py`.
This real-Chrome check creates a disposable sample copy, changes only its
fixture session record, and verifies that `· Running` appears and disappears
without reloading Home. It makes no provider calls.

## A13 project header

With a fresh `provider_fixture:app` on port 8001 and the normal UI on 5173, run
`uv run --with playwright python browser_checks/header.py`. It checks the full
project name and header reflow at 1280, 1100, 700, 390 and 320px, the absence of
the workspace tagline, shared Home/Close button states, the existing functional
connection disclosure in its compact project-header presentation, disclosure/
focus behavior, and keyboard Back to home. It verifies the desktop 3×2
Difficulty/Model/Thinking and About/Google/ChatGPT arrangement. About matches
the compact Home pill and sits directly below Difficulty. On narrow screens,
the header reflows to two columns with About still beneath Difficulty. It cycles
and persists model/thinking settings (including explicit effort reconciliation
when a new model does not support the current effort), relative cost disclosure,
noninteractive Google placeholder, functional ChatGPT connection disclosure/
actions, and no horizontal overflow. Screenshots
are `/tmp/sigma-a23-model-controls-*.png` and
`/tmp/sigma-a13-header-*.png`.

## T131 / T23.1 Google OAuth browser acceptance harness

Run `uv run --with playwright python browser_checks/t23_1_google_signin.py`.
The check starts its own API and Vite servers on free loopback ports and uses
temporary project, state, and workspace roots. It requires frontend npm
dependencies (`npm ci --prefix frontend`) and installed Chrome or Chromium
(`SIGMA_BROWSER_EXECUTABLE` can select another executable). The browser
intercepts only Google auth status, login, logout, denied status, and the local
budget response; protected project API requests reach the real API through the
test-only deterministic identity adapter. It covers anonymous and revoked
identity denial, fixture sign-in, reload persistence, logout, account
switching, rejected identity, per-account project isolation, and the project
header at desktop and mobile widths. Redirects and identities are local
fixtures; this does not verify Google, deployed cookies, or hosted OAuth.

## Nonconsecutive Subset Sums sample review

With the local SIGMA UI running, run
`uv run --with playwright python browser_checks/nonconsecutive_sample.py`.
This check opens the existing **Nonconsecutive Subset Sums Modulo 3** sample,
reviews its five saved sessions and collapsible outcome sections, checks the
exported research report, and checks 390px and 320px layouts for horizontal
overflow. It reads saved evidence only and makes no model/provider calls.
Screenshots are written to `/tmp/sigma-nonconsecutive-desktop.png` and
`/tmp/sigma-nonconsecutive-mobile.png`.

## A15 single-request Generate Strategy

Start a fresh `provider_fixture:app` on port 8002 and keep the normal UI on
5173, then run `uv run --with playwright python browser_checks/a15_generate.py`.
It verifies one bounded request from an empty counting project with an empty
starting point, an editable unsaved draft, cancellation without mutation,
provider failure and its single dismissible toast, immediate retry while the
cancelled provider fixture is still delayed, explicit save/reopen,
existing-strategy context and immutable sample source.
The provider is entirely mocked. Review captures are
`/tmp/sigma-a15-review-1440.png` and `-390.png`.

`uv run --with playwright python browser_checks/strategies.py` also checks the
collapsible sidebar, compact and draggable project-description divider, and
existing strategy interactions at desktop and narrow widths. It uses the same
fresh fixture on port 8002.

## Original A15 text representations (separate implementation)

Run the normal Vite UI on `127.0.0.1:5173`, then start a fresh isolated mock
provider (`uv run uvicorn browser_checks.provider_fixture:app --host 127.0.0.1
--port 8001`). Run `uv run --with playwright python browser_checks/text_views.py`.
The script opens the sample Nonconsecutive example into the fixture's managed
copy, checks automatic Plain/Markdown conversion on selection, rendered math,
in-place title/description edits and stale retries,
cache reuse without conversion requests, desktop/mobile overflow and source
fixture immutability. It uses no paid provider call. Restart the fixture before
rerunning, since the script intentionally edits its managed sample copy.

## A14.2 ChatGPT-plan Markdown conversion regression

Keep the normal UI running on `127.0.0.1:5173`. Start a fresh isolated mock
provider with `uv run uvicorn browser_checks.provider_fixture:app --host
127.0.0.1 --port 8002`, then run
`uv run --with playwright python browser_checks/a142.py`. The browser check
verifies the Σ tooltip, one dismissible failed-request toast, retained Plain
source with no artifact, and explicit successful retry. It makes no live
provider call; the first local conversion response is deliberately failed and
the retry goes through the fixture.

## A17 / A17.1 / A17.2 project titles and research sessions

Keep the normal UI running on `127.0.0.1:5173`. Start a fresh isolated
`provider_fixture:app` on port 8002, then run
`uv run --with playwright python browser_checks/a17_research.py`. The real-Chrome
check covers inline title edits, cross-workspace mutual exclusion (rapid clicks,
keyboard entry, cancel, and save failure), New/Generate auto-expansion and focus,
Strategies control order, Back to Home, and connection dialog portal/backdrop/
focus/Escape behavior with blocked underlying controls. Session rows do not
collapse, while activity and artifact details remain inspectable. It also checks
generated-title review/save, non-destructive legacy fallback, billing consent,
three-cycle research, navigation/reopen, pause/resume/stop during delayed fixture
work, failure recovery, concurrent provider pulse and reduced motion,
desktop/mobile layout, and unchanged strategy data. It makes no live provider
call. Screenshots are written to `/tmp/sigma-a171-desktop.png` and
`/tmp/sigma-a171-mobile.png`.

## T17.8 archived answer-free session projection

Run `uv run --with playwright python browser_checks/t17_8_saved_session.py`.
The check starts its own API and Vite servers on dynamically selected local
ports, mounts a temporary copy of the archived T17.8 project/session export,
and opens it in real Chrome. It verifies the ended session, provisional
positive/unverified outcome, mathematical solution review, verification caveat,
and saved artifacts. It also checks that expanding/collapsing the session does
not move the Sessions count and that the Export Project dialog offers no LaTeX
report choice. It sends no session-start or provider request and removes only
its own temporary files and processes.

## T29 Human feedback during research

With the normal UI on port 5173 and a fresh isolated `provider_fixture:app` on
port 8002, run `uv run --with playwright python
browser_checks/t29_intervention.py`. This real-Chrome check verifies the vertical
Type and agent radio groups, Type → For → Strategy ordering, and feedback
submission during a fixture-backed session. It verifies submission makes no
additional provider call, checks per-target acknowledgment/audit provenance, and
checks the narrow mobile layout. The deterministic service scenarios in `tests/research_sessions.py`
add concurrent strategy, safe-boundary delivery, pause/resume, restart recovery,
supersession and terminal rejection coverage. These are local fixtures and make no
live provider calls. Screenshot: `/tmp/sigma-t29-intervention-mobile.png`.

## T43.1 enabled strategy session set

With Vite running on `127.0.0.1:5173` and a fresh isolated provider fixture on
port 8022, run
`SIGMA_BROWSER_FIXTURE_URL=http://127.0.0.1:8022 uv run --with playwright
python browser_checks/t43_1_strategy_selection.py`. Real Chrome creates a
temporary project with three strategies, disables strategy rows, confirms an
over-budget enabled set is rejected, and checks that the start request includes
exactly the currently enabled strategies. The start request is intercepted, so
no research session or provider inference call is started. The check also
verifies confirmation actions stay in the Strategies heading slot and that the
layout fits 1440px and 390px viewports.

## A20 AI-authored research paper

Start the current Vite frontend on port 5174 and the isolated mock provider/API
on port 8012 in separate terminals:

```sh
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5174
```

```sh
uv run uvicorn provider_fixture:app --app-dir browser_checks --host 127.0.0.1 --port 8012
```

Then run:

```sh
uv run --with playwright python browser_checks/a20_paper.py
```

This real-Chrome scenario copies the Maximum Regions Sample, runs its mock
research session, opens paper authoring through Export Project → Academic paper
using LaTeX, checks saved
snapshot and claim references, and retrieves the compiled PDF through the
browser. It also checks the narrow-screen dialog. It makes no live provider
calls. Review captures are `/tmp/sigma-a20-paper-preview.png` and
`/tmp/sigma-a20-paper-mobile.png`; the downloaded PDF is
`/tmp/sigma-a20-paper.pdf`.

## T45 long-form Xenopus paper

Run the Vite frontend on port 5181 and the isolated mock provider/API on port
8015, then run:

```sh
SIGMA_T45_UI_ORIGIN=http://127.0.0.1:5181 SIGMA_T45_FIXTURE_PORT=8015 \
  uv run --locked --with playwright python browser_checks/t45_long_paper.py
```

This real-Chrome check opens the Xenopus sample, verifies the compact paper
dialog at desktop and 390px mobile widths, starts long-form authoring directly
without a browser-native confirmation, injects a temporary failure and verifies
that Generate is available for retry, then checks in-dialog cancellation and
focus behavior. It authors a long-form paper using the deterministic local
provider fixture and checks the bounded completed-preview scroll area and both
PDF modes: the “Open in browser tab” option returns an inline PDF, while the
default still returns an attachment. No live model or paid usage is involved.
The PDF is saved at `/tmp/sigma-t45-xenopus.pdf`; dialog captures are in
`docs/evaluations/t45-paper-dialog/`.

## T40 Google account and administrator controls

Run the normal SIGMA UI and then run
`uv run --with playwright python browser_checks/t40_cloud_ui.py`. This real
Chrome check intercepts Google identity and authorization APIs with deterministic
test fixtures, so it makes no Google OAuth or provider calls. It exercises the
signed-out, administrator and member screens, the Google account dialog,
administrator add/edit/save/revoke actions, and desktop/mobile layout. Screenshots
are written to `/tmp/sigma-t40-admin-home-{1440,390}.png` and
`/tmp/sigma-t40-admin-dialog-{1440,390}.png`.


## Outcome modes and Project Settings layout

`outcome_hierarchy.py` uses real Chrome with local copies of the saved
Nonconsecutive Subset Sums and Maximum Regions projects. Set
`SIGMA_OUTCOME_PROJECTS_ROOT` to a directory containing
`nonconsecutive-subset-sums-8.sigma` and
`maximum-regions-by-lines-3.sigma` copies. The copies must have each saved
session's `project_path` rebound to its copied project directory. The check
writes its preference only to those copies.

Start the API with isolated temporary data and the UI on a separate port:

```sh
SIGMA_PROJECTS_ROOT=/tmp/sigma-outcome/projects \
SIGMA_STATE_DIR=/tmp/sigma-outcome/state \
SIGMA_AUTH_HOME=/tmp/sigma-outcome/auth \
uv run uvicorn sigma.api:app --host 127.0.0.1 --port 8178
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5178 --strictPort
```

Then run the actual Chrome check:

```sh
SIGMA_OUTCOME_PROJECTS_ROOT=/tmp/sigma-outcome/projects \
SIGMA_OUTCOME_UI_ORIGIN=http://127.0.0.1:5178 \
SIGMA_OUTCOME_API_ORIGIN=http://127.0.0.1:8178 \
uv run --with playwright python browser_checks/outcome_hierarchy.py
```

It covers default Simple mode, historical summaries, qualifications and
verification, per-project Preferences save/reload/isolation, Advanced disclosure
order, Reasoning / proof Markdown rendering, and computational source/output
access, narrow Outcome rendering, and the Model/Thinking side-by-side desktop
and stacked mobile layouts. This is browser
emulation at 390px and 320px, not physical-phone testing.


## Project creation request and About math-formatting regressions

With the local UI running, execute these real-Chrome checks:

```sh
SIGMA_BROWSER_BASE_URL=http://127.0.0.1:5193 uv run --with playwright python browser_checks/project_create_contract.py
SIGMA_BROWSER_BASE_URL=http://127.0.0.1:5193 uv run --with playwright python browser_checks/about_math_formatting.py
```

The project-creation check intercepts the create request and verifies the
frontend sends the Outcome preference in its successful create payload. It
also confirms the default local ChatGPT control is enabled; the existing
`t23_1_google_signin.py` check covers the configured local OAuth gate. The
`t43_1_strategy_selection.py` check also guards the Project workspace against
React's maximum-update-depth loop while exercising live strategy/session
controls. The About check verifies the AI-assisted mathematical formatting
description and dialog fit at desktop and narrow mobile widths. API behavior is
fixture-backed; no real credentials or provider calls are used.
