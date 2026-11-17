# SIGMA Personal ChatGPT — shared Docker service

SIGMA's Personal ChatGPT worker supports **real account authentication and
real inference** locally and in the opt-in hosted deployment. The historical
two-container synthetic laboratory is separate; it is not a provider in
production.

## How real sign-in works

1. The SIGMA user must authenticate with Google and have an active workspace.
2. Clicking the ChatGPT connection pill starts a private, disposable Chromium
   browser inside the **one shared Personal Docker container**. SIGMA displays
   that browser through an authenticated, same-origin noVNC stream. OpenAI is
   never embedded in an iframe.
3. Chromium opens the real OpenAI account chooser. OAuth uses a
   `127.0.0.1` callback *inside the same container* (not a public redirect).
   This loopback route functions on a remote GCE VM as well as Docker Desktop.
4. SIGMA switches to Personal only after the user-owned worker confirms the
   account and available models. The backend binds inference to the verified
   Google subject and workspace HMAC. No bearer token is returned to React.
5. Selecting Sponsored disconnects that Personal authorization when confirmed;
   clicking Sponsored again launches a **fresh** account chooser. Closing the
   temporary browser never revokes a successfully retained account.

The shared worker image uses
`SIGMA_PERSONAL_SHARED_VAULT=1` and
`SIGMA_PERSONAL_SHARED_REAL_SIGNIN=1`. Its synthetic test routes are not
mounted, and legacy `SIGMA_AUTH_POC_LAB`,
`SIGMA_AUTH_POC_LOCAL_DOCKER`, and
`SIGMA_AUTH_POC_REAL_SIGNIN` are **not** prerequisites for real hosted
sign-in. The container still requires a properly configured per-workspace
HMAC seed and private broker.

## Local developer run

```sh
./sigma start --prod
```

This starts SIGMA, its local host broker and the same shared Personal
browser/worker. It does not use the Mac's existing OAuth tokens as fallback.
Docker Desktop must be running. Use the SIGMA connection pill for real sign-in.

## Hosted production run

Use the reviewed production deployment files:

- `deploy/personal-shared.compose.yaml` and
  `deploy/personal-shared.gce.yaml` — the isolated shared worker, loopback
  ports, memory limits and persistent encrypted records
- `deploy/systemd/sigma-personal-broker.service` — the root-owned host
  supervisor exposing authenticated Unix relays to backend UID 10001
- `deploy/compose.personal.backend.gce.yaml` — the feature-gated backend
  socket mounts (never the Docker daemon)
- `deploy/HOSTED_PERSONAL_ACCEPTANCE.md` — activation sequence, release
  verification, multiuser isolation, restart and rollback checks

Hosted Personal is **disabled by default** in SIGMA's backend until the
operator sets `SIGMA_PERSONAL_HOSTED_ENABLED=true` and provisions the
protected HMAC seed, stable checkout ID and attested shared-worker image.
The GCE backend overlay sets `SIGMA_PERSONAL_BROWSER_ENABLED=1` (the
production flag), not the local `SIGMA_PERSONAL_BROWSER_LAB_ENABLED`.
The legacy lab flag remains available for existing `./sigma start --prod`
workflows, but is not consulted for hosted Personal authorization.
The existing sponsored model remains available while Personal is disabled.
Enabling the feature must never imply provider entitlement or successful
sign-in: verify a real hosted account and complete a real inference request
during acceptance testing before promoting the release.

## Synthetic CI and legacy laboratory

`auth-poc/synthetic_signin.py` is used only by isolated security tests and
the legacy standalone synthetic laboratory. Its fake account has no model
entitlement; it cannot satisfy real Personal account verification.

`auth-poc/test_shared_oauth_lifecycle.py` runs against the shared runtime
with a mocked OpenAI authorization URL and verifies that a real chooser is
issued, no old cached account silently completes an explicit new attempt, the
synthetic chooser is inaccessible, and user A cannot control user B's browser.
Additional container tests verify encryption, worker isolation and inference
binding without using real customer credentials.

## Security and release boundary

The Chromium browser has a different UID from the worker that holds encrypted
credentials. User records and keys persist on the protected state disk.
The external noVNC and model ports are loopback-bound only. Backend-to-broker
and backend-to-worker access uses private Unix sockets and authenticated
workspace identities. SIGMA must never expose the browser port, mount the
Docker daemon inside the backend, or use a host-level Personal token fallback.

A successful local OAuth or synthetic CI run does **not** establish that
OpenAI approves ChatGPT-plan use by a remotely hosted multiuser service.
Provider eligibility and a real hosted end-to-end run are explicit release
acceptance gates; see `deploy/HOSTED_PERSONAL_ACCEPTANCE.md`.

The legacy two-container laboratory can still be run with
`./auth-poc/start.sh` for synthetic tests. It is not the shared
production path.
