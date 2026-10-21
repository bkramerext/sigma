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

## A9 recents and dialog actions

Start a fresh `provider_fixture:app` as above, then run
`uv run --with playwright python browser_checks/recents.py`.
This check expects a fresh disposable fixture state so it can verify one-time
Included example labeling. It measures action-button bounds at 1280x720,
1440x900, 390x844 and 320x700 while scrolling, showing errors and holding a save.
It also exercises actual sample opening, five UI creations, LRU eviction, reopen,
missing/corrupt entries and forgetting. Captures are `/tmp/sigma-a9-*.png`.
`settings.py` remains the shared-form persistence/focus regression.
