# T172 authentication and account-isolation readiness assessment

**Assessment:** **BLOCKED for production launch**. Offline implementation and
fixture acceptance are substantial, and this review found no new deterministic
security defect in the examined auth boundary. The real hosted OAuth and
two-identity acceptance needed to establish production readiness remain
unverified. Do not interpret fixture success or closed implementation tickets
as production acceptance.

## Evidence reviewed

- **T66 / issue #66:** integrated in PR #169. Service tests and local Chrome
  cover independent ChatGPT account records and switching, fixture Google A/B
  login, reload/logout/denial, and project isolation. The existing handoff notes
  that the ChatGPT Cancel-button browser interaction and full live Google ×
  ChatGPT cross-product were not verified. It explicitly preserves the hosted
  403 restriction on personal ChatGPT auth.
- **T131:** closed as offline preparation only. The runbook defines the
  production Google Web client and callback and a desktop hosted procedure;
  live OAuth and hosted cookie behavior were deferred.
- **T134:** closed as offline preparation only. Its required hosted A/B matrix
  (projects, direct API references, writes, sessions, artifacts, Recent,
  accounting, switching and durable mappings) remains unrun with real
  identities.
- Source review of `cloud_auth`, `cloud_workspaces`, storage configuration, the
  API middleware, ChatGPT auth, and provider selection. No T163 implementation
  was changed.

## Deterministic evidence from this assessment

- `tests/cloud_auth.py`: **PASS**, 16 tests. Covers trusted OAuth flow state,
  callback claim validation and replay, authorized/denied accounts, session
  persistence/expiry/logout revocation, account switching, Origin rejection,
  and hosted personal-ChatGPT-auth rejection.
- `tests/cloud_workspaces.py`, `tests/cloud_research.py`,
  `tests/cloud_research_api.py`, `tests/cloud_research_sponsored_api.py`:
  **PASS** during `./sigma test`; owner isolation, unauthorized references,
  restart/recovery, accounting, and fixture provider behavior.
- `tests/storage.py`: **PASS** during `./sigma test`; persistent-disk
  two-subject isolation, restart, backup/restore and fail-closed roots.
- `uv run --locked --with playwright python
  browser_checks/t23_1_google_signin.py`: **PASS** in installed Chrome using
  deterministic local identities and a temporary test API/storage. It covered
  sign-in, reload, logout, anonymous/revoked denial, denied identity, account
  switch, and owner-specific project workspaces. It did not contact Google.
- `./sigma test`: **FAIL overall**. Auth, storage, workspace and cloud research
  scenarios passed. Three existing deployment assertions in
  `tests/deployment_package.py`, `tests/gce_host.py`, and
  `tests/host_monitor.py` expect `srv-sigma\\x2dstate.mount`, while the current
  service uses `RequiresMountsFor=/srv/sigma-state`. Frontend typecheck also
  initially lacked installed `tsc`. After `npm ci --prefix frontend`, separate
  frontend typecheck and production build **PASS**; the full suite skipped its
  build step because of earlier failures. A second full-suite run, with other
  checkouts running the same broad suite concurrently, additionally failed
  `tests/research_sessions.py` on its shared worker-active lock; auth tests
  still passed. This is recorded as a suite contention result, not an auth
  failure.

## Required OAuth configuration checks

The operator must verify in the approved Google Cloud project and deployment
environment, without copying secrets into evidence:

1. The selected project is the owner-approved production OAuth project; the
   inventory's `SIGMA Auth` project is not by itself proof of the intended
   project.
2. OAuth client type is **Web application**, distinct from localhost clients.
3. Authorized JavaScript origin is exactly
   `https://sigma-research.duckdns.org`.
4. Authorized redirect URI is exactly
   `https://sigma-research.duckdns.org/api/cloud-auth/callback`.
5. Consent app identity, support contact, audience and Testing/Production
   publication policy are approved; if Testing, each named test user is listed.
6. Requested scopes are limited to `openid`, `email`, and `profile`.
7. `GOOGLE_OIDC_CLIENT_ID` matches that Web client. The corresponding secret is
   available only through the named Secret Manager secret
   `sigma-google-oauth-client-secret` and the backend secret-file mechanism;
   runtime IAM grants only required access. Do not print/read back the value.
8. `SIGMA_CLOUD_PUBLIC_ORIGIN` is the canonical HTTPS origin;
   `SIGMA_CLOUD_AUTH_ENABLED` is on; `SIGMA_CLOUD_ADMIN_CONTACT_EMAIL` is the
   exact verified authorized administrator and approved invitation contact.
9. Hosted mode has no local-auth fallback. `/api/cloud-auth/status` reports
   `enabled=true`, `ready=true`, `target="hosted"`; DNS, HTTPS certificate,
   callback and deployed release SHA refer to the same host/release.

These are console and deployed-environment checks, not claims that this
assessment observed their production values.

## Exact checklist for the first live hosted sign-in

Use only after the owner authorizes a hosted test window and the named test
identities. Record UTC time, tester, deployed SHA, canonical origin, desktop
Chrome version, identity role labels and sanitized evidence references. Use
separate clean browser profiles; never copy cookies. Use disposable marked
projects only; do not trigger research, paper generation, or provider spending.

1. Confirm OAuth configuration items 1–9 above with the owner. Confirm status
   endpoint values, HTTPS hostname/certificate and deployed SHA. Stop if any
   mismatch or status is not ready.
2. In profile A, sign in with the approved designated administrator. Confirm
   Google returns through the exact HTTPS callback and SIGMA displays the
   expected account and admin role. Confirm URL ends at the app and contains no
   code, state, nonce or token.
3. Reload, close/reopen the browser, and revisit the app. Confirm the same
   identity and only its own Recent/projects remain available.
4. Sign out. Confirm signed-out UI; `/api/projects/recent` returns 401 before
   and after reload; the former session cookie no longer authorizes access.
5. In a clean profile, confirm anonymous access to protected Recent/project
   APIs returns 401 with no private data. Attempt a forged identity header and
   confirm it does not change the principal.
6. In an isolated profile, sign in with the owner-approved Google identity
   that lacks a SIGMA grant. Confirm “Access not yet granted”, no authenticated
   session and no protected project access.
7. In profile A, sign in as the administrator, create a disposable marker
   project, then use “another Google account” to switch to the distinct
   authorized member identity. Confirm the prior session is invalidated and
   only the member's Recent/projects appear. Switch to the denied identity and
   confirm no access remains.
8. Complete the T134 hosted A/B privacy matrix before declaring account
   isolation accepted: direct cross-owner reads/writes/downloads, owner-state
   before/after comparisons, Recent, sessions/artifacts and durable mapping.
   Use only already-saved sessions unless provider calls are separately
   authorized.
9. Record PASS/FAIL/BLOCKED/UNVERIFIED per row, observed statuses/states,
   sanitized evidence, UTC end time and elapsed time. Do not capture emails,
   project contents, tokens, cookies or authorization parameters. Escalate any
   unexpected disclosure, stale-session access, cross-owner mutation, or
   callback mismatch as a launch blocker and stop the live run.

## Remaining acceptance gaps requiring real identities

- Real authorized designated admin, authorized member, and valid-but-unauthorized
  Google account; their distinct stable Google subjects and approved roles.
- Actual production OAuth project/client/consent/test-user settings, secret
  delivery and least-privilege runtime access, without exposing secret values.
- Real HTTPS browser round trip, callback routing, Secure cookie behavior,
  deployed expiration/revocation and auth behavior across the actual host.
- Full hosted T131 denied/anonymous/switching matrix and T134 A/B state,
  direct-reference and denied-write non-mutation matrix on the deployed SHA.
- Hosted persistence across actual service/container restart and the separately
  authorized backup/recovery operation. Local fixture restart/restore is not
  evidence for GCE disk behavior.
- T66's ChatGPT Cancel-button browser acceptance and any real ChatGPT auth
  acceptance, if product release requires it. This does not authorize personal
  ChatGPT authentication in hosted mode.

## Security findings and launch decision

**No new launch-blocking code defect identified by this offline review.** The
reviewed code has server-side OAuth state/nonce/claim checks, exact-origin
validation for state-changing requests, Secure/HttpOnly/SameSite hosted
cookies, hashed server-side sessions with an eight-hour expiry and revocation,
current-grant checks, owner-bound workspace mapping, and a hosted-mode 403 for
personal ChatGPT auth. Deterministic tests exercise these boundaries.

**Launch remains blocked by missing production evidence**, not by an inferred
test failure: no real Google callback, real identity authorization/denial,
deployed session/cookie behavior, hosted A/B privacy run, or hosted persistence
recovery evidence is present. Any failed result in the live checklist is a
security launch blocker. No policy change or exception is recommended here.

No live OAuth, provider call, production credential access/change, infrastructure
provisioning, or hosted policy change occurred.
