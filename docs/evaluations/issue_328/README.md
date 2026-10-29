# Issue #328 — Paper generation progress browser evidence

Real Chrome was run against the local Vite UI and the deterministic
`browser_checks.provider_fixture` API. Provider replies are synthetic; no live
or paid inference was used. The fixture delayed paper-schema responses to make
active states observable without simulating intermediate progress.

| Capture | What it shows |
|---|---|
| [short-progress.png](short-progress.png) | One-shot writing state, elapsed display, and Cancel generation control. |
| [long-progress.png](long-progress.png) | Long-form evidence stage with the actual count, 1 of 3. |
| [reconnected.png](reconnected.png) | Refresh interrupted the stream; the dialog recovered the saved cancellation stage and elapsed state. |
| [complete.png](complete.png) | Retried long-form generation reached PDF compilation and published a saved version with PDF links. |

Run the browser acceptance from the repository root with:

```sh
SIGMA_PAPER_PROGRESS_FIXTURE_DELAY=1 \
SIGMA_PAPER_PROGRESS_FIXTURE_ORIGIN=http://127.0.0.1:5181 \
uv run uvicorn provider_fixture:app --app-dir browser_checks --host 127.0.0.1 --port 8015

SIGMA_API_TARGET=http://127.0.0.1:8015 \
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5181 --strictPort

SIGMA_T328_UI_ORIGIN=http://127.0.0.1:5181 \
uv run --with playwright --no-sync python browser_checks/issue328_paper_progress.py
```

The fixture-origin option exists only in `provider_fixture.py` and rewrites the
origin for the test API to the already trusted local Vite origin. It is disabled
by default. The browser captures are review examples, not production data.
