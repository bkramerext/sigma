# T131 production Google OAuth readiness

**Assessment:** Prepared for the first hosted test; production configuration
and hosted authentication are **UNVERIFIED**. Do not treat repository
configuration, local fixtures, or operator inventory as proof of saved Google
Cloud settings. No live Google OAuth or production configuration access/change
was performed for this assessment.

## Evidence-backed configuration checklist

| Requirement | Required value or check | Evidence and current assessment |
|---|---|---|
| Google Cloud project | Human owner must designate the production OAuth project. The runbook records `SIGMA Auth` / `sigma-auth-512601` / `665111821572` as an existing OAuth project, but says this does not decide whether it is the approved production client project. | **UNVERIFIED / operator decision required.** Do not infer from the name or from the separate infrastructure project `sigma-research-prod`. |
| Consent screen | Approved app name and support contact; owner-approved audience and Testing/Production policy; if Testing, explicitly list each authorized tester. | **UNVERIFIED.** No consent-screen inspection evidence is recorded. |
| OAuth client | OAuth client type **Web application**, associated with the owner-approved production project and distinct from localhost clients. | **UNVERIFIED.** No production Web client is recorded as created. |
| JavaScript origin | `https://sigma-research.duckdns.org` exactly (no path or trailing slash). | **Required, not observed saved.** |
| Redirect URI | `https://sigma-research.duckdns.org/api/cloud-auth/callback` exactly. | **Required, not observed saved.** |
| Scopes | `openid`, `email`, `profile` only. The current auth implementation requests `openid email profile`. | **Implementation confirmed; consent/client configuration unverified.** |
| Client ID | `GOOGLE_OIDC_CLIENT_ID` in root-only `/etc/sigma/deploy.env` must identify the selected production Web client. | Deployment contract confirmed; deployed value uninspected. Do not copy it into evidence. |
| Client secret | Secret Manager secret `sigma-google-oauth-client-secret`, with an active version provided by its authorized owner; delivery through `deploy/fetch-secrets.sh` to `/run/sigma-secrets/google-oauth-client-secret`, owned by UID/GID `10001`, mode `0400`, then mounted as `/run/secrets/google_oidc_client_secret`. | **Blocked / unverified.** `docs/OPERATION_RUNBOOK.md` and `docs/CLOUD_DEPLOYMENT.md` record that the OAuth secret had not been created as of 2026-10-25 because Secret Manager required an initial version value. No secret was inspected. |
| Runtime IAM | Attach dedicated `sigma-runtime` service account; grant `roles/secretmanager.secretAccessor` on the OAuth secret resource only (and separately on the OpenAI secret required by the packaged backend). No project-wide secret access, key, Owner or Editor grant. Confirm API enabled, active secret version, runtime identity attachment, and successful file delivery/healthcheck without reading/logging payload. | **Documented target; actual OAuth secret binding/version and delivered file unverified.** Cloud deployment docs describe this narrow resource-level IAM. |
| Hosted environment | `SIGMA_CLOUD_AUTH_ENABLED=true`; `SIGMA_CLOUD_PUBLIC_ORIGIN=https://sigma-research.duckdns.org`; required exact `GOOGLE_OIDC_CLIENT_ID`; `SIGMA_GOOGLE_OIDC_CLIENT_SECRET_FILE` resolves via Compose to the mounted secret; the designated admin/contact address is set. | Compose enforces required client ID, secret mount and designated admin/contact; target origin/auth are set by deployment. **Production environment not inspected.** |
| Designated administrator and contact | Set `SIGMA_CLOUD_ADMIN_CONTACT_EMAIL` to the exact verified email of the human-approved initial administrator. Its first valid Google subject binds the account as admin. This same address is shown as the invitation contact. Record the role label only in evidence; do not record the email. | Required by Compose and code; production value and subject binding **unverified**. The configured admin is configuration-bound and cannot be revoked through Access Management. |
| Authorized members / denied identity | After admin bootstrap, configure exact approved member email entries in SIGMA Access Management; prepare a separate valid Google identity with no SIGMA grant for the denial test. Do not use broad domain grants unless explicitly approved. | Supported by current auth behavior; production grants and owner-approved test identities **not confirmed**. |
| DNS / VM / HTTPS | Host must resolve to the independently verified VM external IP; certificate and deployed release must serve that same hostname. | The current operator runbook has DNS A-record / external-IP verification pending and says not to infer it from the reserved IP alone. Coordinator and human are independently verifying; **do not use DNS as a readiness assumption**. |
| Hosted status | From a network external to the VM, `GET https://sigma-research.duckdns.org/api/cloud-auth/status` must return `enabled=true`, `ready=true`, `target="hosted"`; capture HTTP status, UTC time and deployed release SHA without identity details. | Runbook provides a read-only check. No current hosted status response or deployed SHA has been verified here. |

## Runtime behavior and failure handling

Code inspection confirms that `/api/cloud-auth/login` returns HTTP 503 when
hosted auth configuration is not ready. The status endpoint exposes readiness
without secret values or the designated administrator email. When auth has an
internal error,
protected routes return 503; unauthenticated protected requests return 401
and clear the session cookie. Invalid/unverifiable Google claims fail with
401. A valid Google identity without a SIGMA grant is redirected to the
“Access not yet granted” state, with no authenticated session. State/nonce,
issuer, audience, signature, expiry, verified-email and stable-subject checks
are enforced server-side. Hosted `/api/ai/*` remains 403; do not enable personal
ChatGPT authentication in hosted mode.

On any preflight mismatch, unavailable endpoint, non-hosted target, or
`ready=false`, stop before Google sign-in and record **BLOCKED** with the safe
error/status and release SHA. On callback failure, unexpected principal/role,
unexpected session persistence/revocation, or any private data disclosure,
stop the live run, do not retry or broaden grants, preserve only sanitized
evidence, and escalate as a launch blocker. Do not put callback query strings,
Google codes, tokens, cookies, email addresses, secret values, or project
contents into logs/screenshots/PRs. A denied account must not leave an old
authorized session usable.

## Exact first-live-sign-in procedure

Run only after the operator confirms the production settings above, the
independent DNS/IP verification is complete, HTTPS and the deployed release
are ready, and the owner authorizes a test window plus named identities. This
procedure is acceptance work, not authorization to change configuration.

1. Record UTC start, tester, Chrome version, origin, deployed SHA and redacted
   identity role labels. Confirm the OAuth project, consent policy, Web client,
   origin, callback and scopes in the approved console. Confirm secret resource
   and resource-level runtime IAM without exposing the value. Confirm bootstrap
   and member grants with the owner.
2. From outside the VM, verify public DNS against the independently confirmed
   external IP, HTTPS hostname/certificate and same-origin app/API routing.
   Fetch `/api/cloud-auth/status`; require HTTP success and `enabled=true`,
   `ready=true`, `target="hosted"`. Record release SHA. Stop if any check fails.
3. Use clean desktop Chrome profile A for the approved designated administrator
   and profile B for a distinct authorized member. Use one isolated profile for
   the valid-but-unauthorized identity. Never copy cookies or reuse profiles.
4. In profile A, select **Sign in with Google** and complete the real Google
   round trip. Confirm the HTTPS callback reaches the app, the expected admin
   role is present, and the final address bar contains no `code`, `state`,
   `nonce`, or token. Record result only; do not capture callback parameters.
5. Reload and close/reopen profile A. Confirm the same account remains signed
   in and sees only its own Recent/projects. Repeat reload/reopen in profile B
   and confirm its expected member role and private Recent/projects.
6. Sign out in A. Confirm signed-out UI and `/api/projects/recent` returns 401
   before and after reload. A formerly valid session cookie must not authorize
   requests. In a clean anonymous context, require 401 for Recent and protected
   project APIs; a forged identity header must not change the principal.
7. Sign into the denied identity in its isolated context. Require the
   “Access not yet granted” UI, no authenticated session, and 401 for protected
   project APIs. Return to A; sign in as admin and create one disposable,
   clearly marked project. Switch through **Use another Google account** to
   member B. Require the admin session invalidated and only member-owned
   projects visible. Switch to the denied identity and confirm no old session
   remains usable.
8. Complete the separate T134 hosted A/B matrix for direct cross-owner reads,
   writes, downloads, Recent, sessions/artifacts, usage and no-mutation checks
   before claiming account-isolation acceptance. Use only saved sessions;
   provider-backed research is outside this sign-in procedure.
9. Record PASS/FAIL/BLOCKED/UNVERIFIED for each step, UTC end and elapsed time,
   observed status/UI, sanitized evidence references and any deviations.
   Stop and escalate on disclosure, stale access, cross-owner mutation,
   unexpected role or callback mismatch. Do not claim acceptance when a row is
   unverified.

Acceptance requires all OAuth configuration rows verified by the operator,
the expected hosted status on a known deployed SHA, successful admin and member
round trips, correct denied/anonymous/revoked behavior, and completed T134
privacy checks. This is still separate from launch go/no-go and hosted
persistence/recovery acceptance.

## Human authorization blockers

- Owner must designate the production OAuth project/client and approve the
  consent-screen app name, support contact, audience and publication/testing
  policy.
- Authorized Google Cloud operators must configure/save the Web client,
  exact origin/callback and scope consent, create the named Secret Manager
  resource/version through the approved secret-entry flow, and grant
  resource-scoped runtime access. These production changes are explicitly
  outside this assignment's authority.
- Owner must select the exact designated administrator/contact,
  approve member and denied test identities, and approve a hosted test window.
- Coordinator/human must finish independent DNS/external-IP verification;
  deployment owner must provide a known release SHA, ready hosted status, and
  HTTPS evidence. These must be established before any real identity is used.
- T134's two-user privacy matrix and any separately authorized persistence/
  recovery checks remain required before broader hosted acceptance.

## Source record

Reviewed current `main` at `a335f3f`, `docs/T172_AUTH_READINESS.md`,
`docs/T131_HOSTED_OAUTH_ACCEPTANCE.md`, `docs/OPERATION_RUNBOOK.md`,
`docs/CLOUD_DEPLOYMENT.md`, `deploy/compose.yaml`, `deploy/fetch-secrets.sh`,
`deploy/gce_preflight.py`, `src/sigma/cloud_auth.py`, and
`tests/cloud_auth.py`. Runbook and inventory entries are operator-reported
snapshots dated 2026-10-25, not live console or VM observations.
