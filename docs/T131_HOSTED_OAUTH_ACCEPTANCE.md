# T131 hosted Google OAuth acceptance

**State:** Preparation only. Do not use this checklist as evidence of a live
sign-in. Run it only after the deployment is ready and the operator has
authorized the hosted test window and the named Google identities. No Google
Cloud Console, OAuth client, secret, IAM, or hosted endpoint changes are part
of this preparation.

## Production OAuth settings Brian must configure

In the owner-approved Google Cloud project, configure an OAuth consent screen
with the approved app name, support contact, audience, and production/test-user
policy. Confirm the selected project/client location with the deployment owner:
the inventory lists `SIGMA Auth` (`sigma-auth-512601`) separately from the
infrastructure project; it does not establish which project should own the
production client. Add only the scopes SIGMA requests (`openid`, `email`,
`profile`). Add each authorized test identity under the consent-screen policy
when the app remains in Testing; otherwise publish according to the approved
audience policy.

Create or select an OAuth client of type **Web application**, separate from any
localhost client. For the selected production host, configure exactly:

- **Authorized JavaScript origin:** `https://sigma-research.duckdns.org`
- **Authorized redirect URI:**
  `https://sigma-research.duckdns.org/api/cloud-auth/callback`

Do not add a path to the origin, a trailing slash, HTTP, localhost, an IP
address, or alternate callback spellings. Confirm the DNS hostname and HTTPS
certificate serve the same origin before acceptance. Copy the client ID to
root-only `/etc/sigma/deploy.env` as `GOOGLE_OIDC_CLIENT_ID`. Store the client
secret as the named Secret Manager secret
`sigma-google-oauth-client-secret`, grant the runtime identity access only to
that secret, and expose it to the backend through the existing secret-file
path. Never put the secret in this repository, a PR, screenshots, logs, or
chat. Configure `SIGMA_CLOUD_ADMIN_CONTACT_EMAIL` as the exact verified
email for the authorized initial administrator; this is also the approved
invitation contact. The
deployment sets `SIGMA_CLOUD_PUBLIC_ORIGIN` from the HTTPS hostname and enables
hosted auth; do not enable local auth fallback.

These are application requirements, not proof that the settings have been
saved. The owner should verify the OAuth client project, type, origin, callback,
consent-screen audience/test-user status, client ID association, secret
availability, and designated administrator identity in their approved
consoles. Do not export or share secret values.

## Repeatable desktop procedure

Record a UTC start time, tester, browser/version, public origin, deployed
release SHA, and authorized test identity references (redacted). Use a current
desktop Chrome or Chromium browser. Create two clean browser profiles (A and B)
and keep them separate; never copy cookies. Use an authorized admin in A and an
authorized member in B where available. Use only disposable, clearly marked
test projects. Do not start research, paper generation, or any paid/provider
action under this OAuth check.

1. **Preflight:** Open the public origin and verify HTTPS certificate/hostname.
   Request `/api/cloud-auth/status`; require `enabled=true`, `ready=true`, and
   `target="hosted"`. Record the HTTP result and deployed SHA from the operator
   release record. If this fails, stop and record the row as blocked.
2. **Sign-in and callback:** In profile A, choose **Sign in with Google**, pick
   the named identity, and complete consent if Google presents it. Require
   return to SIGMA with the expected role and identity. Confirm the callback
   reaches the exact HTTPS URI above and ends at the app, without a state,
   nonce, code, or token left in the address bar. Do not capture authorization
   codes or cookies. Repeat in profile B with its distinct identity.
3. **Session persistence:** In each profile, refresh, close/reopen the browser,
   and revisit the origin. Require the same account to remain authenticated
   until explicit sign-out/expiry, with that owner's Recent/projects available.
   Record redacted project IDs or hashes only. This checks browser persistence;
   any service restart/reboot persistence check belongs to its separately
   authorized deployment operation.
4. **Sign-out:** Sign out in A. Require the UI to return to signed-out state and
   the protected `/api/projects/recent` request to return `401`. Reload and
   repeat the protected request to show the prior session is invalidated.
5. **Unauthorized access:** In a clean signed-out profile, request
   `/api/projects/recent` and another protected project endpoint. Require
   `401`, no private data, and no access from forged identity headers. Public
   status and the explicitly public Demo may remain readable.
6. **Rejected identity:** Use an owner-authorized identity that is valid at
   Google but absent from SIGMA's grants, in an isolated profile. Require the
   “Access not yet granted” state; no authenticated session or project access;
   protected requests remain `401`. Record only the role/result and redacted
   identity reference. Do not revoke a real user as a test substitute.
7. **Account switching:** In profile A, sign in as an authorized account,
   confirm its identity and a disposable private marker, then choose **Use
   another Google account** and select a second authorized identity. Require
   the first session to be invalidated, the second identity to appear, and only
   the second account's Recent/projects to load. Also switch from an authorized
   identity to the rejected test identity and require no remaining access.

For A/B project, direct API, denied-write/no-mutation, workspace, artifact,
usage, and extended persistence checks, continue with the [T134 hosted privacy
matrix](T134_HOSTED_ACCEPTANCE.md). Do not treat its offline fixtures as hosted
evidence.

## Evidence record

For every step record **PASS / FAIL / BLOCKED / UNVERIFIED**, UTC timestamp,
observed HTTP status or visible state, and a sanitized evidence reference.
Screenshots must exclude email addresses, project contents, authorization
parameters, browser storage, cookies, and tokens. Preserve the actual deployed
SHA, origin, desktop browser/version, identity role labels (A/B/admin/member/
denied), exact callback URI checked, and outcome. Attach console/operator
confirmation that the OAuth settings above match; do not attach secret values.

```text
Ticket: T131
Host/origin and deployed release SHA:
UTC start/end and elapsed:
Tester; desktop browser/version:
OAuth project/client setting confirmation (no secrets):
Identity A/B/denied: authorized role and redacted reference:
Sign-in/callback:
Session persistence:
Sign-out and stale-session denial:
Anonymous/forged identity access:
Rejected identity:
Account switching:
Sanitized evidence references:
Failures, deviations, remaining dependencies:
Provider calls/costs: none for this procedure
```

Hosted acceptance requires an actually deployed release and operator evidence
for every row. Required dependencies currently include saved production OAuth
configuration and secret delivery, approved named test identities including a
denied identity, a reachable HTTPS deployment with matching callback, and a
known deployed SHA. Any unavailable identity or operation stays UNVERIFIED;
this document and deterministic local tests do not satisfy hosted acceptance.
