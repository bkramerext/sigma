# Cloud authentication for SIGMA

Cloud identity is opt-in. Local SIGMA keeps its existing ChatGPT sign-in and
continues to use its current single-user API behavior when
`SIGMA_CLOUD_AUTH_ENABLED` is unset or false. Hosted Google identity is not an
AI-provider credential and does not authorize inference. The current cloud mode
blocks `/api/ai/*`; a future hosted provider design must provide explicit user
authorization and billing controls.

Set these deployment environment values to enable cloud authentication:

| Variable | Purpose |
|---|---|
| `SIGMA_CLOUD_AUTH_ENABLED=true` | Explicitly enables hosted authorization. |
| `SIGMA_CLOUD_PUBLIC_ORIGIN=https://sigma.example.org` | Exact public HTTPS origin, with no path or trailing slash. Used for callback and CSRF origin validation. |
| `GOOGLE_OIDC_CLIENT_ID` | Google OAuth web client ID. |
| `GOOGLE_OIDC_CLIENT_SECRET` | Google OAuth web client secret; keep server-side only. |
| `SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL` | Verified email permitted to establish the first administrator. Its first Google subject is permanently bound in the auth database. |
| `SIGMA_CLOUD_ADMIN_CONTACT_EMAIL` | Public contact address used to prefill an invitation request. SIGMA opens a mail draft and never sends it. |
| `SIGMA_CLOUD_AUTH_HOME=/var/lib/sigma-auth` | Absolute, service-owned private directory; mode 0700. The SQLite database is mode 0600. |
| `SIGMA_CLOUD_DEMO_AUDIT=/opt/sigma/cloud-demo/handshake-demo-audit.json` | Absolute path to the curated, server-owned, read-only Project Audit v2 snapshot served to guests. It is separate from private project storage and required for the public Demo. |

Create a Google OAuth client for a web application. Register the exact redirect
URI `${SIGMA_CLOUD_PUBLIC_ORIGIN}/api/cloud-auth/callback`. SIGMA uses Google's
fixed OIDC discovery document, authorization-code flow, PKCE S256, state and
nonce. It validates the ID-token signature using Google's published JWKS and
requires the Google issuer, exact client audience, unexpired token, matching
nonce, stable subject, and `email_verified: true`. It rejects multi-audience
tokens and mismatched authorized-party claims.

After setup, the configured bootstrap address can sign in once to bind its stable
Google subject as administrator. Administrators can add exact email entries or
exact email domains in Access Management. Entries authorize accounts; no email
is delivered. Domain rules compare the complete verified-email domain after
case normalization, so suffix/lookalike domains do not match. An explicit
revoked email rule takes precedence over a domain allow rule. Revocation is
checked on every request and removes matching active sessions. Re-adding a
revoked email reactivates that exact entry. The bootstrap admin remains
configuration-bound and cannot be revoked in the UI.

Sessions are random opaque values stored only as SHA-256 digests in SQLite.
Cookies are `Secure`, `HttpOnly`, `SameSite=Lax`, host-only `__Host-` cookies,
and expire after eight hours. State/nonce/verifier records are one-use and
expire after five minutes. Unsafe requests require the configured exact Origin.
The auth database contains no provider tokens or project data.

Cloud sign-in controls appear in the existing Home header above Projects, and
the authenticated identity controls stay in the existing Home/project headers.
The legacy Google placeholder is not shown. When a valid Google identity is not
authorized, the app displays “Access not yet granted” in the SIGMA Home design.
Only that denied flow can read its verified email: the server keeps it in a
short-lived private-database record behind an opaque `Secure`, `HttpOnly` cookie
for up to ten minutes. It is not returned by status, does not create a session
or workspace, and is deleted when Use Another Account starts a fresh
`prompt=select_account` login. The screen offers the `/demo` guest-route
handoff and a prefilled `mailto:` invitation request to the configured contact.
The contact address is intentionally public; access rules and other accounts
remain private. `/demo` serves the same read-only curated project to anonymous
visitors, denied identities and signed-in users. Its dedicated API accepts no
project ID or filesystem path: it loads only `SIGMA_CLOUD_DEMO_AUDIT`, a
service-owned saved audit snapshot kept outside private project storage. The
snapshot contains the project, saved strategies, sessions, outcomes, research
evidence and analysis. JSON audit and Text/HTML/LaTeX reports are generated from
that snapshot without models, agents, computation, per-visitor copies or writes.
Keep the configured file read-only to the service and review its contents before
deployment; missing or invalid configuration makes the Demo unavailable.

T22.2 adds identity, API access checks, invitation administration, and the
minimal access UI. It does not provision per-user project roots, migrate project
storage, isolate existing filesystem paths by owner, schedule durable work, or
deploy a cloud service. All authorized users still reach the existing project
service/storage surface; do not treat this ticket as a completed multi-tenant
workspace or a deployment-ready public service. Those boundaries remain for
later cloud work. Cloudflare feasibility and deployment are separate from this
authentication implementation.

Automated tests use local RSA signing keys and mocked Google endpoints. They do
not make network requests or paid model calls. No Google OAuth client, client
secret, allowed organization domain, or admin email is hardcoded in source.
