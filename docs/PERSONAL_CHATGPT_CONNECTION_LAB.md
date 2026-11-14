# Personal ChatGPT production-style connection lab

Status: **design / not implemented**. This document defines a truthful localhost
reproduction for a connection method potentially usable by remotely hosted SIGMA.
It is **not** approval for hosted OAuth, credential sharing, or ChatGPT plan usage
beyond OpenAI's documented eligibility.

## Operator requirements

1. `./sigma start` retains exactly its existing Personal ChatGPT account-chooser,
   account stores, provider routing, pill appearance and research behavior.
2. `./sigma start --prod` exercises the **new** connection method locally
   end-to-end, not the "Oh, Darn." explanatory dialog. It does not reach production,
   reuse the ordinary localhost credential directory, use an OpenAI API key or
   silently select SIGMA sponsorship.
3. The user chooses *any eligible account offered by OpenAI*, without an email
   allowlist. The model connection must be bound to the actual verified account.
4. No application to OpenAI for additional permissions. Never use an unapproved
   public HTTPS OAuth callback or fake `127.0.0.1`/redirect origin.
5. Preserve per-user Google identity, SIGMA access, projects, paper/session
   resumability, explicit funding/provider choice and the existing two-row pill.

## Current constraints

The OSS Sign in with ChatGPT registration specifies an HTTP callback on
`127.0.0.1` with path `/auth/callback`. This callback belongs to the machine
running the browser. It cannot simply be replaced with the hosted SIGMA HTTPS
callback. SIGMA's present cloud research admission also uses a deployment-wide
sponsored provider, not a Personal credential for the signed-in Google user.

OpenAI documents local authorization followed by secure credential transfer for
**an open-source tool on a self-hosted VM**, with separate persistent host IDs.
The documentation does not explicitly extend that method to operating a shared
remotely hosted multi-user application. Do not equate a successful VM import
experiment with such authorization.

References:
- https://developers.openai.com/siwc/token-sharing-open-source
- https://developers.openai.com/siwc/token-sharing-open-source/sign-in
- https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms

## Proposed --prod MVP: two-process local companion rehearsal

Start both components on **localhost**, but treat them as separate machines and
security principals. They must use *different* state/credential directories.

```
local browser: SIGMA UI (hosted control-plane simulator)
        | existing SIGMA Google identity + Personal selection
        | one-time, identity-bound companion pairing
        v
local SIGMA backend (no access to Personal ChatGPT tokens)
        ^ authenticated outbound companion channel
        |
local SIGMA Personal companion (separate process, own 0700/0600 storage)
        | existing OpenAI account chooser + 127.0.0.1 PKCE callback
        | model discovery and eligible inference
        v
OpenAI
```

The same outbound companion protocol should work against the hosted SIGMA
control plane **without** exposing OAuth tokens to SIGMA's web server. Production
requires the user to install and run the Personal companion; this is a
constraint, not a hidden workaround. An offline companion must pause Personal
jobs safely, not move them onto sponsorship or an API key.

### Pairing contract

- SIGMA backend creates a random, short-lived, single-use pairing intent bound
  to the authenticated **Google subject** and Personal selection. Do not identify
  the user by email alone.
- Companion initiates the outbound authenticated connection and claims that
  intent. Bind it to the caller's verified SIGMA identity; ensure TLS, replay
  resistance, rotation/revocation and strict origin handling before production.
- OpenAI sign-in is completed *only in the companion*, using existing SIWC
  loopback/PKCE/nonce/ID-token validation. No OAuth code or token passes through
  the SIGMA browser, Google login endpoints, project bundles, logs or the
  remotely hosted control plane.
- The backend stores only the provider identity/connection status, per-user
  routing lease, request IDs and bounded execution/accounting metadata.
- Provider work must use the companion actually paired to that Google subject;
  the sponsor store, another user's companion and API-key paths are forbidden
  as fallbacks.
- The UI reuses exactly the established Personal/Sponsored pill implementation.
  Status reflects real companion + provider readiness; no new pill variants.

### Execution and recovery

- Persist queued jobs before dispatch, provider attempt IDs and acknowledgments,
  and the bound Personal connection identity.
- On transport loss, preserve work and any *uncertain* provider attempt;
  do not automatically replay possibly-dispatched calls.
- On Stop, prohibit new dispatches after acknowledgement; reconcile in-flight
  work conservatively. Maintain SIGMA's resumability requirements.
- Separate per-user personal usage reporting from the shared sponsor budget.
- Confirm no research is sent when disconnected, guest, mismatched or unpaired.

## Required local acceptance

1. Run normal `./sigma start --signin --navigate` with an existing Personal
   connection. Record connected mode and check a permitted model. Stop. Verify
   its private store remains unchanged by the rehearsal.
2. Run `./sigma start --prod --signin --navigate`. Observe two isolated
   processes/stores and complete the new companion pairing. Select a ChatGPT
   account in OpenAI's **actual** chooser. Test a permitted model call using
   companion-held credentials only.
3. Switch to another eligible ChatGPT account. Verify actual returned identity,
   scopes and inference account binding; never infer it from requested email.
4. Start a small Session and confirm Investigator/Skeptic dispatch through the
   companion; Stop, inspect attempted calls and durable state.
5. Disconnect the companion mid-job, restart it and verify safe pause/Resume,
   including a provider-unknown attempt and no replay.
6. Try different local Google users, a replayed pairing request, expired pairing,
   signed-out browser, a guest, a spoofed callback and a mismatched worker.
   All must fail without disclosing tokens or crossing workspaces.
7. Restart SIGMA without `--prod` and demonstrate the original direct local
   OAuth and Personal account connection still works unchanged.

### Non-goals / failure conditions

- Do not label a UI-only notice or a simulated connected pill as success.
- Do not change `SIGMA_CLOUD_INFERENCE_PROVIDER` to mask lack of Personal routing.
- Do not copy private OAuth tokens into the browser or to the shared multi-user VM.
- Do not silently depend on user devices staying online: disclose that Personal
  inference pauses when the companion disconnects.
- Do not claim background cloud execution survives laptop shutdown under this
  design. A genuinely supported and authorized per-user cloud-worker extension
  would require separate assessment.
- Do not merge/deploy a partially wired system or compromise ordinary local
  Personal mode.

## Implementation order

1. Separate runtime profiles for `start` and `start --prod`, with tests proving
   no crossover between standard credentials and rehearsal state.
2. Standalone local companion using SIGMA's existing sign-in and inference
   components, with a local fake-control-plane transport.
3. Secure, identity-bound pairing and outbound transport shared by localhost
   simulation and future production; test replay and disconnect paths.
4. Per-user provider routing, observability, durable dispatch/recovery.
5. Real browser acceptance in local `--prod` mode, CI, then separate production
   review for deployment eligibility.
