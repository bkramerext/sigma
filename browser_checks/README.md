# A7 browser checks

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
This check expects a fresh disposable fixture state. It covers the default
Stock Projects tab, keyboard tab switching, direct stable stock opens without a
dialog, retained edits, exclusion from Recents, unavailable and forget behavior,
source-file immutability, and 1280x720, 390x844 and 320x700 layouts. Captures
are `/tmp/sigma-a11-*.png`.
`settings.py` remains the shared-form persistence/focus regression.

## A13 project header

With a fresh `provider_fixture:app` on port 8001 and the normal UI on 5173, run
`uv run --with playwright python browser_checks/header.py`. It checks the full
project name and header reflow at 1280, 1100, 700, 390 and 320px, the absence of
the workspace tagline, shared Home/Close button states, identical Home/workspace
connection pill styling and live label, disclosure/focus behavior, and keyboard
Close. Screenshots are `/tmp/sigma-a13-header-*.png`.

## A14 agentic strategy and project layout

Start a fresh `provider_fixture:app` on port 8001 and keep the normal UI on
5173, then run `uv run --with playwright python browser_checks/agentic.py`.
The fixture state must be fresh because this check opens and saves in the stable
stock project. It verifies the empty counting project, ordered live progress,
unsaved cancellation, explicit acceptance/reopen, a distinct second mechanism,
and immutable source data. The provider is entirely mocked. Review captures are
`/tmp/sigma-a14-review-1440.png` and `-390.png`.

`uv run --with playwright python browser_checks/strategies.py` also checks the
collapsible sidebar, compact and draggable project-description divider, and
existing strategy interactions at desktop and narrow widths.
