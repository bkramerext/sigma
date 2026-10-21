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
