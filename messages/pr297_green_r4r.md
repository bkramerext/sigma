# GREEN R4R — PR #297 local admin sponsor pill

Status: **R4R**. Repository: `bkramerext/sigma`. Branch:
`coordinator/signin-session-playback-stabilization`.

## Current implementation commit SHA

`aa3aeecc051d27e5d7c4a9ef20d0fc49eecc1d54` (parent
`3dc199dcbeca77ba6c913a0a973b7245494491ab`).

## Diagnosis and correction

The pill's local personal-mode branch submitted the active ChatGPT account ID
to `/api/ai/auth/begin`. When that saved registration was the designated
sponsor, the API returned the reproduced 403. `expected_email()` also inferred
the sponsor identity from the Google administrator address when the explicit
sponsor setting was absent.

Local connection status now includes a boolean identifying when the active
registration is the explicitly configured sponsor. The admin pill uses
`/api/ai/sponsor-auth/begin` for that registration and selects sponsored mode
after successful authorization, so the resulting status is Connected. A
genuinely personal saved account continues through `/api/ai/auth/begin` and
keeps personal mode. `SIGMA_CLOUD_SPONSOR_EMAIL` is now required to identify a
sponsor; it is never inferred from Google identity. The API keeps its
role-based admin guard for sponsor renewal, rejects members, and leaves the
sponsor record unchanged on denial. Sponsor OAuth begins after releasing the
credential-store transaction.

## Tests executed and results

- `uv run --locked --no-sync python tests/cloud_auth.py CloudAuthTests.test_local_admin_pill_request_routes_selected_sponsor_to_sponsor_oauth CloudAuthTests.test_local_expired_personal_connection_does_not_switch_funding_and_admin_can_renew`
  — passed, 2 tests. The first posts the same account selection and local
  Google-admin identity observed in the reproduction; the member denial also
  verifies the sponsor token is unchanged.
- `uv run --locked --no-sync python tests/cloud_sponsor.py` — passed, 19 tests,
  including OAuth callback exchange, sponsor credential persistence, connected
  status, explicit sponsor identity configuration, and the API connection
  marker used by the frontend.
- `uv run --with playwright --no-project python browser_checks/local_admin_sponsor_pill.py`
  — passed in Chromium. Actual pill clicks verify the admin sponsor request
  route, the generic route's simulated 403 is avoided, sponsor OAuth completion
  reports connected, and a genuinely personal account uses the personal route
  without switching to sponsored mode.
- Scoped Ruff check/format, `npm run typecheck --prefix frontend`, and
  `git diff --check` — passed.
- The broader `browser_checks/hosted_sponsored_connection.py` was attempted but
  stopped at its welcome-dialog assertion: expected `$0.04 remaining`,
  while the fixture rendered the invitation welcome without that allowance
  text. The new focused browser check above passed.

## Remaining unverified behavior

Live Google login, ChatGPT OAuth/token exchange, and provider connectivity were
not tested; OAuth completion and credentials are simulated. No full CI wait,
paid calls, merge, or deployment occurred. R4R is reported to the coordinator
through the human, per the collaboration rules.
