# Hosted ChatGPT sponsor connection (#200)

The designated sponsor is configured privately through
`SIGMA_CLOUD_SPONSOR_EMAIL`. Google OIDC grants
SIGMA workspace access; it does not issue OpenAI model credentials. The sponsor
must separately authorize ChatGPT plan use. Changing an OpenAI email does not
create this authorization.

## Implementation

- Hosted authenticated model discovery and connection checks reach the
  provisioned provider instead of the blanket cloud 403. The designated
  sponsor OAuth flow is restricted to verified SIGMA administrators.
- `SIGMA_CLOUD_INFERENCE_PROVIDER=chatgpt` explicitly selects a dedicated
  sponsor credential store. An absent, mismatched, revoked, or unavailable
  sponsor session never falls back to an API key or local operator account.
- `SIGMA_CLOUD_SPONSOR_EMAIL` pins the verified sponsor email independently
  of the public admin contact. SIGMA checks it before refresh and after refresh.
- Import verifies the OpenAI ID token signature, issuer/audience/expiry and
  verified identity, granted plan scopes, token metadata and access expiry.
  Only the selected registration is imported. The VM host ID is preserved.
- A shared explicit-provider validator gates research, proposals, agentic
  generation, papers, and text conversion; stale account/project bindings fail
  before dispatch. Hosted readiness accepts the configured sponsor identity.
- Existing durable user/global token, concurrency, and spending guards still
  apply to ChatGPT-funded requests. Dollar allowances are SIGMA admission
  estimates, not a measurement of the sponsor's remaining ChatGPT plan usage.

## One-time production provisioning

Configure these non-secret deployment settings:

   ```dotenv
   SIGMA_CLOUD_INFERENCE_PROVIDER=chatgpt
   SIGMA_CLOUD_SPONSOR_EMAIL=your-sponsor@example.test
   ```

Replace the placeholder privately; never commit the actual address. Backend
startup logs flag missing sponsor configuration.

Compose sets `SIGMA_CLOUD_CHATGPT_AUTH_HOME` to
`/var/lib/sigma-auth/chatgpt-sponsor` on the persistent state volume. Do not
copy local or personal credential files. A signed-in SIGMA administrator uses
the hosted sponsored connection pill to start the dedicated sponsor ChatGPT
authorization flow. The sponsor completes sign-in in the browser; the verified
callback writes credentials directly to the persistent store. The existing
API-key secret mount may remain for explicit API-key deployments, but it is
never read or used in ChatGPT mode.

Check `/api/cloud-research/connection` for provider `chatgpt` and status
`connected`, then `/api/cloud-research/readiness` for a clear sponsored
preflight. These are non-inference checks; do not dispatch a research call
without separate authorization.

## Evidence and remaining acceptance

The authenticated production browser reproduced the blanket 403 on 2026-10-26
before this change, after Google administrator access succeeded. The account's
Recent list was empty, so the original persisted #201/#202 project was not
available through that account's history. No provider inference was dispatched.

This PR is not production acceptance: deployment, sponsor authorization and
protected VM provisioning, actual provider catalog success, and original-project
retests remain unverified. No existing credentials were read or transferred in
the implementation environment.
