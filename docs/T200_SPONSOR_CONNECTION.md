# Hosted ChatGPT sponsor connection (#200)

The designated sponsor is `zetacontinuation@gmail.com`. Google OIDC grants
SIGMA workspace access; it does not issue OpenAI model credentials. The sponsor
must separately authorize ChatGPT plan use. Changing an OpenAI email does not
create this authorization.

## Implementation

- Hosted authenticated GET `/api/ai/models` and `/api/ai/connection` now reach
  the provisioned provider instead of the blanket cloud 403. All hosted
  account-changing and OAuth routes remain blocked, including for admins.
- `SIGMA_CLOUD_INFERENCE_PROVIDER=chatgpt` explicitly selects a dedicated
  sponsor credential store. An absent, mismatched, revoked, or unavailable
  sponsor session never falls back to an API key or local operator account.
- `SIGMA_CLOUD_SPONSOR_EMAIL` pins the verified sponsor email independently
  of the public admin contact. SIGMA checks it before refresh and after refresh.
- Import verifies the OpenAI ID token signature, issuer/audience/expiry and
  verified identity, granted plan scopes, token metadata and access expiry.
  Only the selected registration is imported. The VM host ID is preserved.
- Existing durable user/global token, concurrency, and spending guards still
  apply to ChatGPT-funded requests. Dollar allowances are SIGMA admission
  estimates, not a measurement of the sponsor's remaining ChatGPT plan usage.

## One-time production provisioning

Use OpenAI's documented [self-hosted VM procedure](https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms).
This is a protected operator workflow, not a public credential upload endpoint.

1. In local SIGMA, use Continue with ChatGPT and authorize the sponsor's
   account/workspace and plan scopes. Use a dedicated private `SIGMA_AUTH_HOME`
   for this transfer so other local accounts are not included. Authorize
   immediately before transfer; import requires an unexpired ID/access token.
2. Stop local SIGMA to prevent refresh-token rotation races. Transfer its
   protected `credentials.json` to the VM over SSH. Never paste tokens into
   chat, an issue, an environment file, a project, or a public website.
3. Configure these non-secret deployment settings:

   ```dotenv
   SIGMA_CLOUD_INFERENCE_PROVIDER=chatgpt
   SIGMA_CLOUD_SPONSOR_EMAIL=zetacontinuation@gmail.com
   ```

   Compose sets `SIGMA_CLOUD_CHATGPT_AUTH_HOME` to
   `/var/lib/sigma-auth/chatgpt-sponsor` on the persistent state volume.
   The existing API-key secret mount is retained for deployment compatibility;
   it is never read or used in ChatGPT mode. Do not remove other secrets or
   weaken preflight checks.
4. With application writers stopped, run the import as the backend UID 10001
   in a one-off backend container using the same persistent state volume and
   configuration. Mount the transferred file read-only, owned by UID 10001
   with mode 0600, at `/run/sponsor-transfer/credentials.json`, and invoke:

   ```sh
   python -m sigma.cloud_sponsor /run/sponsor-transfer/credentials.json
   ```

   The importer persists a new VM host ID on a fresh store or preserves the
   existing VM ID. It refuses a non-hosted or non-ChatGPT configuration.
5. Remove the temporary transfer file and stop using the source credential
   copy. The VM owns subsequent rotating-token refreshes. Restart the app with
   the reviewed release. A matching Google sign-in can now discover the
   already-provisioned sponsor connection; it does not prompt every user to
   authorize the sponsor again.
6. Check `/api/ai/models` and the sponsored connection panel while signed in.
   The response must classify the actual provider status, preserve project
   settings, and contain no tokens or saved-account list. Discovery does not
   send a research prompt. Paid or plan-consuming generation is a separate
   acceptance step requiring authorization.

## Evidence and remaining acceptance

The authenticated production browser reproduced the blanket 403 on 2026-10-26
before this change, after Google administrator access succeeded. The account's
Recent list was empty, so the original persisted #201/#202 project was not
available through that account's history. No provider inference was dispatched.

This PR is not production acceptance: deployment, sponsor authorization and
protected VM provisioning, actual provider catalog success, and original-project
retests remain unverified. No existing credentials were read or transferred in
the implementation environment.
