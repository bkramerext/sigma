# Issue #289: Operation Narrow Passage funding investigation

## Result

The deterministic regression copy of **Operation Narrow Passage v2** uses the normal SIGMA sample-copy, research-session worker, sponsored job, SQLite inference ledger, saved evidence, and portable-project export paths. Provider responses are deterministic local fixtures; there were no external or paid calls.

With an isolated global ceiling of $0.06, two fixture calls settled at $0.025 each. The next call required a conservative $0.03 reserve, while only $0.01 remained. The ledger refused the third call before provider dispatch. This happened even with the test administrator's per-user allowance treated as unlimited: that flag does not bypass the configured global ceiling. The session is now visibly paused with the exact ledger reason. After increasing only the isolated fixture ceiling to $0.20, SIGMA resumed the same session, retained the two completed calls and their evidence, did not replay them, and finished the remaining Investigator/Skeptic pair.

This reproduces a real and deterministic denial path and demonstrates safe recovery. It does **not** establish that the inaccessible production Session #1 was denied by the global ceiling. The production project's complete export, session JSON and corresponding ledger rows were not available in the checkout or connected Drive. The issue's narrative alone cannot distinguish a project cost cap, global ceiling, sponsorship allowance, unknown held reservation, or provider-side refusal.

## Portable bundles

- [`deterministic-funding-denied.json`](exports/deterministic-funding-denied.json) — importable project bundle captured after the third call's not-dispatched refusal and before replenishment. Session status: `paused`; calls used: 2; settled estimate: $0.05.
- [`deterministic-funding-resumed.json`](exports/deterministic-funding-resumed.json) — importable bundle from the same project and session after replenishment. It retains the not-dispatched attempt and original evidence, then completes the remaining two calls. Session status: `ended`; calls used: 4; estimated cost: $0.10; outcome remains partial/incomplete and makes no solution claim.
- [`exports/manifest.json`](exports/manifest.json) — IDs, capture method, test limits, safety review and omissions.

To inspect either bundle, download the JSON file and use SIGMA Home → **Import** → choose the JSON file. Import creates a separate project; existing projects are not replaced. The denial bundle and resumed bundle are separate immutable snapshots. They share project and session IDs by design.

## Production records and live execution

The original production project/session export is still needed to determine the exact production denial. The source should be exported from SIGMA's Project → Report / Export → Importable project action while authenticated as `zetacontinuation@gmail.com`, then transferred through an access-controlled location. Before any public artifact, credentials, authentication material, personal account data and sensitive provider payloads must be removed or redacted without removing the relevant session limits, reservation state, saved turns/findings, branch reasons, and sanitized ledger diagnostics.

No production credentials or ledger access were present in this workspace. No live Google sign-in or paid Sol/High request was made. The requested explicit ceiling for a live run is pending; the deterministic test limits are not a production-setting change. Production sponsorship, project, and global limits were not changed.

## Verification

- `uv run --project . python tests/cloud_research.py` — passed, including the new global-reservation pause/resume flow.
- `uv run --locked --no-sync python tests/research_sessions.py` — passed.
- `./sigma test` — passed all steps; the existing graph-present sandbox scenario skipped because its local Docker image is unavailable.
- `uv run --with playwright python browser_checks/t95_paused_session.py` — real Chrome passed stopped/paused guidance, reload, guarded resume and responsive checks. This does not exercise live provider authentication or billing.
- `npm --prefix frontend run build` — passed.

No live research claim or mathematical success is asserted by the fixture run.
