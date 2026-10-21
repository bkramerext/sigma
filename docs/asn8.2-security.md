# A8.2: ChatGPT-plan authorization and billing separation

Verified documentation on 2026-10-20:

- [OSS overview](https://developers.openai.com/siwc/token-sharing-open-source)
  and [registration/sign-in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in).
- [Discovery](https://auth.openai.com/.well-known/openid-configuration): issuer,
  authorize, token, JWKS and revocation endpoints were actually fetched and matched.
- [Accounts/refresh/storage/revocation](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)
  and [token reference](https://developers.openai.com/siwc/token-sharing-open-source/token-reference).
- [Models/inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference),
  [preview restrictions](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations),
  and [recovery](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery).
- [UI guidelines](https://developers.openai.com/siwc/ui-ux-guidelines).

The public GitHub repository API returned HTTP 200, `private:false`, and public
visibility for `bkramerext/sigma`; LICENSE is Apache 2.0. This local OSS deployment
matches the documented client category. Account/plan/workspace eligibility and
actual endpoint entitlement still depend on OpenAI; they were not tested live.
No commercial partner credential, private ChatGPT endpoint, browser cookie,
other application's login files, or ChatGPT key substitution is used.

## Identity and authorization

A UUIDv4 `urn:uuid:` host ID is persisted once in application state and reused
across launches/checkouts/upgrades. It is independent of project UUIDs and launch
readiness IDs. Each sign-in has fresh random state, nonce and S256 PKCE material,
an already-bound 127.0.0.1 callback listener, and a five-minute lifetime. Pending
attempts remain separate from the active account. Callback method/path/host,
Origin when supplied, query multiplicity, state, expiry and single consumption
are checked. The callback server never logs the request target or reflects
provider/code/state/token contents; its response is no-store/no-referrer.

Initial registration uses `dynamic_agent_client`, `agent_name_hint=SIGMA`, the
stable host, the full documented identity/offline/resource/direct scopes and
resource. Code exchange uses the issued client ID, original exact redirect URI,
resource and verifier, with no secret. Returning accounts use the saved issued
client and hints, never create a replacement client implicitly, and must return
the same signed subject/client binding. Client IDs separate workspace
registrations even when subjects/emails coincide. PyJWT 2.10.1 with cryptography
verifies RS256 against bounded trusted JWKS, issuer, audience, expiry, issuance,
nonce and nonempty subject. Granted direct/resource permission is required for
plan use. Missing/invalid credentials never become an active inference session.

Only explicit local JSON POSTs with an allowed frontend Origin mutate accounts
or mode. Begin returns an opaque transaction plus same-origin handoff URL. The
backend's one-use redirect targets only the verified OpenAI authorize endpoint;
retained ID-token hints are never serialized into React. Polling is limited to
the pending auth attempt; there is no ongoing provider polling or inference health
check. Cancellation stops that attempt; project/account binding and synchronous
UI guards prevent stale/duplicate generation. Header sign-in never generates.

## Storage, refresh and disconnect

Portable owner-only files were chosen instead of a platform-specific Keychain
integration: `~/.config/sigma/` is owned 0700; `credentials.json` and its persistent
lock are owned regular 0600/no-follow files. Credentials never reside in project
packages, source control, `.env`, localStorage or Vite. Explicit `SIGMA_AUTH_HOME`
overrides must be outside the checkout/project packages. Vite's child environment
has provider credential variables removed. Secrets are not logged by these
services; account labels are validated ID-token identity metadata.

A cross-process advisory transaction lock covers read, refresh exchange,
validation and atomic fsynced replacement of the full token set. Refresh uses
saved issued client/resource, omits scope, honors `earliest_refresh_at` (Unix
seconds or an ISO timestamp), and validates returning signed identity before
replacement. Near expiry is 60 seconds; an expired token before the earliest
refresh time yields a temporary unavailable state, not early refresh. Terminal
reuse/revocation/expiry errors clear unusable tokens while retaining registration.
Temporary failures retain credentials. Disconnect attempts discovered revocation
with bounded retry and clears local secrets; it explicitly reports when remote
revocation was unconfirmed.

Limits: files protect against other OS accounts, not malicious code already
running as this account. A crash between provider rotation and durable publication
can still require reauthorization. Interrupted code exchange cannot reuse an
already spent code; retry starts a new attempt. Local storage corruption is an
actionable error, never silent credential replacement. There is no app-password
or account system beyond the selected ChatGPT registration.

## Billing, requests and drafts

Mode/account is application preference. Default is disconnected ChatGPT plan,
even when `.env` contains an API key. Only explicit API-mode selection enables
separate key billing. Plan failures, limits, revoked tokens or unsupported
capabilities never switch mode. Model discovery uses the selected credential and
distinct documented shapes, filters curated compatible research models, and
preserves saved IDs and High without substitution. Public model names and API
cost tiers do not establish plan inference entitlement or remaining allowance.

Plan requests use public `/v1/responses`, array user input, instructions,
`store:false`, `stream:true`, strict proposal JSON schema and selected effort;
preview-prohibited fields including max output tokens and previous response ID
are absent. Deadline, bytes/events and schema bounds replace a forbidden token
limit. SSE validates event order/response identity, requires completion and rejects
refusal/failed/incomplete/truncated/oversized results. Unsupported structured
output or model/effort capabilities report a limitation rather than fake success.
API-key mode retains non-streaming Responses with its existing bounds. No tools,
automatic retries, autonomous work or speculative generation are added.

The form keeps seed and draft in memory, resumes one initiating request after
verified auth, and can transfer text to manual writing. Explicit Save Strategy
remains the sole persistence action. Existing schema v6 and provider/model/effort
receipts stay intact; auth secrets/mode are not inserted into research JSON or
historical provenance. Account switching invalidates cached access and pending
intent bindings; request snapshots keep returned provenance honest.

## Verification boundary

Automated checks use generated fixture RSA keys and signed OIDC tokens, a real
loopback callback, mocked bounded provider HTTP, controlled SSE, two fresh
processes contending for one rotating session, and real Chrome. They do not prove
live OAuth, account eligibility, structured-output admission, plan capacity or
billable model quality. No live sign-in was initiated and no plan/API generation
was consumed. Live verification requires an explicit user request.

The sign-in mark is the unmodified official asset downloaded from
https://developers.openai.com/assets/siwc/sign-in-buttons/chatgpt-logo-black.svg;
white-button format and wording follow the official guidelines. Existing SIGMA
artwork and layouts are preserved. A9's recents and dialog-header correction
remain separate work.
