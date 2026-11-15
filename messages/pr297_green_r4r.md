# GREEN R4R — PR #297 Gate 1 correction

Repository: `bkramerext/sigma`

Branch: `coordinator/signin-session-playback-stabilization`

Base: `846848e81d40d8de27aca3306e6bde6e57154e4f`
Implementation commit: `c2f3f70982fbfedec12e6867903f084785d0c716`. The handoff is a subsequent documentation-only commit; the R4R message reports final repository HEAD.

## Cross-user cancellation root cause and correction

`chatgpt_auth.disconnect()` previously looped over the process-global `_attempts`
map and called `cancel()` for every ID. Since attempts from all logged-in
subjects share that map, B disconnecting could cancel Z's personal OAuth or an
administrator's sponsor-maintenance OAuth. The earlier isolation coverage
checked credentials across distinct stores and used fresh TestClients, but did
not keep multiple users' in-memory OAuth attempts pending concurrently while
one disconnected. It therefore did not expose the shared attempt-map side
effect.

Each attempt now records its originating verified Google subject, resolved
credential store, and sponsor/personal intent. Status, cancel, one-use
authorization handoff, and retry validate the current subject and store.
Personal disconnect cancels only pending personal attempts belonging to that
subject/store; it leaves sponsor and other-user attempts alone.

The API regression starts Z personal and sponsor attempts concurrently, has B
disconnect, verifies both remain pending for Z, denies B's status/cancel/retry
operations, and denies using a sponsor retry ID through the personal route.

## Pill hover/action correction

The primary Sponsored ChatGPT pill hover now says briefly that clicking
connects the user's own ChatGPT account. The nested allowance control is a
separate action: its concise hover says it opens sponsorship details, and its
click only toggles those details. Chromium asserts both hover texts and their
click behavior. Member UI/API checks continue to redact sponsor identity.

## Browser to real API and restart coverage

The existing mocked-API rendering test remains. A second deterministic
Chromium scenario runs the frontend through Vite against a real SIGMA API
subprocess. It uses an existing Z Google session with deliberate personal mode,
seeds same-email personal and sponsor registrations into separate durable
stores, and exercises the actual pill requests and real OAuth begin/open/local
callback/attempt endpoints. Only external ChatGPT token validation/catalog
boundaries are simulated; inference calls are not made.

The browser scenario confirms personal disconnect returns to Sponsored ChatGPT
/ Unlimited without changing the shared sponsor credentials; clicking the
primary sponsored pill calls `/api/ai/auth/begin`; simulated personal OAuth
persists Z's same-email registration and changes the selected mode to personal;
admin sponsor maintenance uses `/api/ai/sponsor-auth/begin` and writes only the
sponsor store. The API process is terminated and restarted using the same auth
database and credential home. The existing cookie, deliberate personal mode,
connected identity, and sponsor registration survive. N's real API responses,
main pill hover/accessibility label, and allowance-details UI do not reveal Z's
sponsor email.

## Full-suite fixture findings

The prior local-suite failures were fixture assumptions, not production
failures. At baseline `846848e`:

- `tests/cloud_research.py` failed its unconfigured API-key assertion because
  the repository's default sponsored provider was ChatGPT. With the intended
  API-key provider explicitly selected, baseline advanced and failed in
  `test_json_project_orphan_recovery`: the fixture helper attempted to create
  a child directory without creating its missing parent.
- `tests/deployment_package.py` failed its cloud-service API-key assertion for
  the same implicit-provider reason.
- `tests/storage.py` passed at baseline in this environment; the earlier nested
  failure report came from the cloud-research assumptions, not an independent
  storage defect.

The API-key test suites now explicitly configure API-key mode and a test-only
key. The cloud-research workspace helper creates parent directories. No
production admission, billing, or storage behavior was changed to satisfy
these tests.

## R4R checklist

- **MET — attempt ownership:** Concurrent-user personal/sponsor cancellation,
  cross-owner status/cancel/retry rejection verified in focused API test.
- **MET — pill contract:** Main sponsored hover/action and nested allowance
  detail hover/action verified in Chromium; sponsored member email redaction
  checked in API and UI.
- **MET — real backend sequence:** Same-email Z personal/sponsor OAuth,
  persistent store separation, API restart with same DB/home/cookie, selected
  mode retention, and N redaction verified by local Chromium against the real
  API process.
- **MET — full local suite:** `./sigma test` completed successfully, including
  Ruff, format, Pyright, frontend typecheck, and build. One graph-present
  sandbox scenario reported skipped because the local Docker image is
  unavailable. Vite emitted its existing large-chunk advisory.
- **SIMULATED — external provider boundary:** ChatGPT token exchange/validation
  and catalog validation use deterministic test fixtures. No paid inference or
  provider calls were made.
- **DEFERRED — hosted personal OAuth:** Unsupported by the current hosted
  authorization design and remains blocked; no local/hosted parity claim is
  made.
- **DEFERRED — live play-session acceptance:** The seven live session-playback
  cases remain assigned to the next round.
- **UNVERIFIED — live accounts:** Real Google login, ChatGPT OAuth/token
  validation, provider connectivity, and live allowance availability were not
  exercised.

## Commands executed

- `uv run --locked --with playwright --no-sync python browser_checks/local_admin_sponsor_pill.py` — passed.
- `uv run --locked --with playwright --no-sync python browser_checks/local_auth_real_backend.py` — passed.
- `uv run --locked --no-sync python tests/cloud_auth.py CloudAuthTests.test_personal_disconnect_cannot_cancel_other_users_or_sponsor_oauth_attempts` — passed (1 test).
- `uv run --locked --no-sync python tests/cloud_research.py` — passed.
- `uv run --locked --no-sync python tests/deployment_package.py` — passed.
- `./sigma test` — passed all configured local steps.
- No CI was run or awaited; no merge, deployment, or paid provider calls occurred.
