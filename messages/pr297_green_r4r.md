# GREEN R4R — PR #297 coordinator corrections

Status: **R4R**. Repository: `bkramerext/sigma`. Branch:
`coordinator/signin-session-playback-stabilization`.

## Current implementation commit SHA

`52c103c5c58635ceae58815a4d4da4f5f6b86069` (parent
`b74e9afde2f87aedcb310ac2c0273927cabf1cb8`).

## Corrections

- Restored `cloud_sponsor.expected_email()` compatibility: with local auth and
  no `SIGMA_CLOUD_SPONSOR_EMAIL`, it uses the existing
  `cloud_auth.INVITATION_RECIPIENT` (`zetacontinuation@gmail.com`). No new local
  sponsor configuration is required.
- Corrected the local admin regression to use Google admin
  `zetacontinuation@gmail.com`, a saved ChatGPT registration owned by
  `zetacontinuation@gmail.com`, personal mode selected, and the sponsor setting
  absent. The pill recognizes the selected sponsor registration, starts sponsor
  OAuth, and after simulated completion selects sponsored mode and reports
  connected.
- Restricted `/api/ai/sponsor-auth/begin` to verified Google admins in local and
  hosted modes. Eligible sponsored members cannot start sponsor OAuth directly.
  The generic `/api/ai/auth/begin` also rejects members attempting the saved
  sponsor registration; the test confirms the sponsor token remains unchanged.
- Preserved genuine personal account flow: the Chromium regression confirms a
  different saved personal account still uses `/api/ai/auth/begin` and stays in
  personal mode.

## Tests executed and results

- Two focused `tests/cloud_auth.py` cases — passed. The pill endpoint regression
  removes `SIGMA_CLOUD_SPONSOR_EMAIL`, saves the `zetacontinuation@gmail.com`
  ChatGPT registration, sets the Google admin's mode to personal, and verifies
  `/api/ai/auth/begin` starts sponsor OAuth without a 403. The second verifies
  an eligible sponsored member is denied by `/api/ai/sponsor-auth/begin` while
  the admin can still start it, with the sponsor setting absent.
- `uv run --locked --no-sync python tests/cloud_sponsor.py` — passed, 19 tests,
  including local sponsor identity fallback and connected status after the
  OAuth persistence regression.
- `uv run --with playwright --no-project python browser_checks/local_admin_sponsor_pill.py`
  — passed in Chromium. It exercises the actual local admin pill click from
  personal mode with a saved sponsor registration, avoids the simulated 403,
  and reports `Sponsored ChatGPT; connected` after simulated OAuth completion.
  It also verifies the genuine personal route.
- Scoped Ruff check/format, `npm run typecheck --prefix frontend`, and
  `git diff --check` — passed.

## Remaining unverified behavior

Live Google sign-in, ChatGPT OAuth/token exchange, and provider connectivity
remain unverified; the browser uses simulated OAuth completion. No CI wait,
paid provider call, merge, or deployment occurred. R4R is reported to the
coordinator through the human, per the collaboration rules.

## Follow-up: sponsored-member disconnected state

Implementation commit: `77cb5d94834758940a882764a665f2ebecb20582` on
`coordinator/signin-session-playback-stabilization`.

The disconnected local sponsor pill now gives sponsored members an unavailable
status and administrator reconnection guidance. It is disabled and its click
handler does not start either sponsor or personal OAuth. The verified admin
sponsor reconnection path and genuine personal connection path are preserved.

### Focused verification

- `npm run typecheck --prefix frontend` — passed.
- Two focused `tests/cloud_auth.py` cases covering admin sponsor routing —
  passed (2 tests).
- `uv run --locked --no-sync ruff check browser_checks/local_admin_sponsor_pill.py`
  and Ruff format check — passed.
- `uv run --with playwright --no-project python browser_checks/local_admin_sponsor_pill.py`
  — passed in Chromium. The scenario completes simulated admin sponsor OAuth,
  switches to the disconnected sponsored-member state, checks its unavailable
  status and administrator guidance, and confirms the pill click emits neither
  `/api/ai/sponsor-auth/begin` nor `/api/ai/auth/begin`; it then verifies the
  genuine personal account route.
- `git diff --check` — passed.

Live Google/ChatGPT OAuth and real provider connectivity remain unverified.
No paid calls, CI wait, merge, or deployment occurred. Updated R4R is reported
to the coordinator through the human.

## Follow-up: local admin mode admission and connected identity

Implementation commit: `4b3c71e24b4580096092e888d593165725225130` on
`coordinator/signin-session-playback-stabilization`.

The 503 cause was a pre-selection dependency: `/api/ai/mode` snapshots the
ledger before persisting `mode=sponsored`, but `_spend_ceiling_decimal()` and
`_global_spend_period()` only enabled local pilot defaults when the current
selection was already sponsored. With an eligible Google admin deliberately
in personal mode and no explicit global ceiling, the snapshot incorrectly
required `SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD`. These checks now use verified
local sponsorship eligibility independently of selected mode. The local pilot
still has a bounded $50 monthly global ceiling; explicit configured ceilings
are unchanged. A failing snapshot does not change the selected mode.

The established auth-state behavior selects Sponsored mode for an eligible
admin unless personal mode was explicitly selected. Sponsor connection state
is derived from the saved sponsor session and a catalog check. It now carries
the authenticated account email to `/api/ai/connection` for the pill tooltip;
the models response omits it, and no token is exposed. The pill shows Sponsored
ChatGPT with Unlimited individual allowance initially, then ChatGPT Connected
with the validated account identity after successful connection.

### Focused verification

- Three focused `tests/cloud_auth.py` cases — passed: the existing-cookie
  admin’s default and deliberate personal modes; snapshot 503 leaves personal
  mode unchanged; successful sponsored-mode selection works with no explicit
  global ceiling and reports the bounded `$50` calendar-month ceiling; and the
  local `/api/ai/connection` reports connected plus
  `zetacontinuation@gmail.com` without returning tokens.
- `uv run --locked --no-sync python tests/cloud_sponsor.py` — passed, 19 tests.
  The simulated OAuth callback validates and persists the exact designated
  `zetacontinuation@gmail.com` sponsor identity; subsequent saved-session and
  catalog checks report connected. The models response continues to hide the
  identity.
- `npm run typecheck --prefix frontend` — passed.
- `uv run --with playwright --no-project python browser_checks/local_admin_sponsor_pill.py`
  — passed in Chromium. It checks initial Sponsored ChatGPT / Unlimited,
  sponsor OAuth completion, the Connected label and account-email tooltip,
  the sponsored-member unavailable/no-OAuth state, and the personal route.
- Scoped Ruff check/format and `git diff --check` — passed.

The OAuth code exchange/token validation and catalog check use deterministic
fixtures; real Google/OpenAI sign-in and provider connectivity remain
unverified. No paid calls, CI wait, merge, or deployment occurred. Updated R4R
is reported to the coordinator through the human.

## Follow-up: sponsor identity privacy (current review blocker)

Implementation commit: `794ae30f27f82e83758c4002a214b86d1fd3c8c9` on
`coordinator/signin-session-playback-stabilization`.

Non-admin users in sponsored mode no longer receive `account_label` from
`/api/ai/connection` or `/api/ai/mode`. The response sanitizer fails closed if
the current mode cannot be resolved. Admin responses retain the designated
sponsor identity. The frontend limits “ChatGPT Connected” and the account-email
tooltip to admins; sponsored members see “Sponsored ChatGPT,” their allowance,
and provider state. Disconnected/unavailable/reconnect-required shared sponsor
states do not launch either sponsor or personal OAuth from the member pill.
Members retain the existing personal-selection route when they explicitly
choose to switch.

### Focused verification

- Three focused `tests/cloud_auth.py` cases — passed, including admin identity
  visibility and the `nontrivialzeeros@gmail.com` member receiving no sponsor
  identity from either `/api/ai/connection` or `/api/ai/mode`.
- `uv run --locked --no-sync python tests/cloud_sponsor.py` — passed, 19 tests.
- `npm run typecheck --prefix frontend` — passed.
- `uv run --with playwright --no-project python browser_checks/local_admin_sponsor_pill.py`
  — passed in Chromium. It deliberately injects the sponsor email into the
  member fixture and confirms it is absent from the visible pill, tooltip, and
  accessible label; the disconnected member pill initiates no auth request.
  The same run confirms the admin gets the Connected/email tooltip.
- Scoped Ruff check/format and `git diff --check` — passed.

The seven requested session-playback acceptance cases belong to the next
round and were not implemented here. Live OAuth/provider behavior remains
unverified; no paid call, CI wait, merge, or deployment occurred. R4R is
reported to the coordinator through the human.

## R4R — same-email personal and sponsor credential separation

Current implementation commit SHA: `4632e4a2c604af1a689d60ff38361813f723128a`.
The preceding sponsor-identity privacy, local pilot admission, and
bounded-spend fixes remain in place.

### Defects corrected

- The local Google admin's ChatGPT email was treated as proof of sponsor
  credential ownership. `/api/ai/auth/begin` now always starts personal OAuth;
  it never reroutes based on account email. Sponsor maintenance stays on the
  administrator-only `/api/ai/sponsor-auth/begin` route.
- Local Google-authenticated users previously shared the local sponsor
  credential directory. Personal credentials now live in a private
  subject-derived store, while shared sponsor credentials remain in the
  SIGMA-owned sponsor store. OAuth attempts retain their intended store through
  the callback, and personal disconnect only touches the current user's store.
- The pill now follows the three-state contract: Sponsored ChatGPT,
  Disconnect from ChatGPT, and Connect to ChatGPT. Personal mode has no
  sponsorship or allowance text; sponsored mode has the appropriate allowance.
  Admin sponsor identity and the concise member-safe tooltip/accessibility
  content are asserted. Failed OAuth leaves the current funding mode intact.
- Corrected a stale API test assertion: the connection response's `mode` is the
  provider adapter (`chatgpt`), while funding selection is stored and verified
  separately as `sponsored`.

### Behavioral coverage and executed checks

- `uv run --locked --no-sync python tests/cloud_auth.py CloudAuthTests.test_local_existing_cookie_keeps_same_email_personal_and_sponsor_credentials_separate CloudAuthTests.test_local_z_and_b_admins_have_unlimited_and_n_has_metered_sponsorship CloudAuthTests.test_local_admin_pill_request_routes_selected_sponsor_to_sponsor_oauth CloudAuthTests.test_local_admin_sponsored_mode_transition_uses_bounded_global_pilot CloudAuthTests.test_local_admin_connection_reports_validated_sponsor_identity CloudAuthTests.test_local_personal_mode_cannot_use_or_disconnect_active_sponsor_credential CloudAuthTests.test_connection_choice_persists_per_verified_subject_and_exhaustion_blocks_sponsor`
  — passed, 7 tests. Uses Google Z's existing cookie with deliberate personal
  mode and no `SIGMA_CLOUD_SPONSOR_EMAIL`, simulates the OAuth redirect,
  loopback callback, token validation and persistence using the same ChatGPT
  email for personal and sponsor credentials, then checks actual credential
  routing, sponsor switch, personal disconnect, sponsor preservation, Z/B
  unlimited and N metered allowances, and provider/budget mode admission.
- `uv run --locked --no-sync python tests/cloud_sponsor.py` — passed, 19 tests.
- `uv run --with playwright python browser_checks/local_admin_sponsor_pill.py`
  — passed in Chromium. Asserts the three ChatGPT labels, both Google pill
  states, OAuth request routes and payloads, Connected personal email tooltip,
  sponsor-mode return and allowance, short hover content and accessibility
  label, no member-visible sponsor email despite a deliberately overinclusive
  API fixture, direct personal OAuth for a sponsored user, and canceled-OAuth
  recovery without funding-mode change.
- `npm run typecheck` from `frontend/` — passed.
- Scoped `ruff check`, `ruff format --check`, `pyright` on the changed Python
  modules, and `git diff --check` — passed.

### Remaining unverified behavior

The API sequence reopens a fresh TestClient with the existing cookie and
persistent auth directory; it does not launch a separate OS process. Real
Google/OpenAI OAuth, token validation, provider connectivity, and hosted
personal OAuth were not exercised. No real provider or paid calls were made.
The seven live session-playback acceptance scenarios remain for the next
round. No full CI wait, merge, or deployment occurred.

## Follow-up — hosted OAuth authorization and repository local suite

Current implementation commit SHA: `13b37641746fab0385d127c5170a24614f552711`.
Hosted authorization now rejects the
personal-only `/api/ai/auth/begin` route while retaining the administrator-only
`/api/ai/sponsor-auth/begin` maintenance flow. This preserves the existing
hosted restriction against proxying users' personal ChatGPT OAuth through the
service. Unknown sponsor handoff IDs fail before an authorization URL is
returned.

`./sigma test` was run locally per repository instructions (no CI was run or
awaited). The first full run failed on hosted auth expectations, a Ruff
format/lint issue, a new OAuth test's possibly-unbound polling result, and
unrelated cloud research/storage/deployment fixture assumptions. The hosted
auth gate, test expectation/type warning, and Ruff issue were corrected. After
those changes:

- `uv run --locked --no-sync python tests/cloud_auth.py` — passed, 66 tests.
- `uv run --locked --no-sync python tests/cloud_sponsor.py` — passed, 19 tests.
- Global `ruff check` and `ruff format --check` — passed.
- Global `pyright` — passed with 0 errors, warnings, or informations.
- `npm run typecheck` — passed.
- `uv run --with playwright python browser_checks/local_admin_sponsor_pill.py`
  — passed in Chromium.

The full local runner is not green: `tests/cloud_research.py` and its nested
`tests/storage.py` run assume API-key provider mode while the repository
default is ChatGPT. Under a diagnostic API-key override matching that
assumption, cloud research advances to an existing JSON orphan-recovery
fixture whose parent directory is absent. `tests/deployment_package.py`
likewise asserts API-key behavior without setting provider mode. These
unrelated fixtures were left outside this round. See the matching note in
`docs/STATUS.md`.
