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
use a hosted HTTPS OAuth callback for ChatGPT dynamic registration. OpenAI's
published [registration guide](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
requires a `127.0.0.1` loopback callback for initial registration; a callback
on the remote SIGMA origin is not valid. For a self-hosted VM, OpenAI's
[documented VM procedure](https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms)
is to complete sign-in locally with the same SIGMA client and designated
account, then transfer the selected protected registration to the VM over a
secure channel such as SSH. Do not send the file through chat, GitHub, logs, or
the public app. The operator must explicitly authorize this account transfer.

### Operator steps

The operator does not need to log in to the VM or stage a file there. First,
create an isolated private credential directory on the trusted computer where
SIGMA is checked out, then start local SIGMA with that directory:

```sh
mkdir -m 700 -p "$HOME/.config/sigma-sponsor-transfer"
SIGMA_AUTH_HOME="$HOME/.config/sigma-sponsor-transfer" \
SIGMA_CLOUD_INFERENCE_PROVIDER=chatgpt ./sigma start
```

In the local SIGMA browser, choose **Connect AI → Continue with ChatGPT**, sign
in as the designated sponsor, and grant ChatGPT plan use. Do not connect any
other ChatGPT account in this isolated instance. After SIGMA reports the
connection, stop it with `./sigma shutdown`; this prevents a local refresh from
racing the VM's refresh. Tell the deployment operator that local sign-in is
complete. Do not send the credential file or its contents in chat. The
`credentials.json` file is under the dedicated directory above; when local
Google identity is enabled, SIGMA may place it below an opaque per-user
subdirectory. The deployment operator can transfer the selected file directly
over the existing private IAP/SSH path and run the validating import. SIGMA
transfers only the selected registration and keeps the VM's existing host ID.
The source directory should be removed after production connection and refresh
are verified.

Stage only the selected registration in a protected temporary file on the VM.
Stop backend writers, then run `python -m sigma.cloud_sponsor
/absolute/path/to/credential-file` as the backend user. The importer validates
the signed OpenAI identity, exact designated email, issuer, scopes, expiry and
token metadata; it imports only that registration and preserves the VM's own
host ID. Remove the staged file after a successful import. Never overwrite the
existing credential store with an unchecked file. Verify
`/api/cloud-research/connection` reports provider `chatgpt` and status
`connected`, then check `/api/cloud-research/readiness`; these checks do not
dispatch inference.

The hosted sponsored connection pill must not start an unsupported remote
OAuth callback. It identifies the active deployment provider and gives the
operator the supported provisioning steps. The existing API-key secret mount
may remain for explicit API-key deployments, but it is never read or used in
ChatGPT mode.

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
