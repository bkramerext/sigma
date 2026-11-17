# Hosted Personal ChatGPT — Red acceptance gate

This is **not** enabled in production by default. Keep SIGMA 0.4.3 in human
acceptance testing until a real, user-owned hosted sign-in and inference call
succeed, including the provider's hosted-use eligibility requirements.

The production worker runs as one memory-bounded Docker service, separately from
the backend/frontend Compose stack. A root-owned systemd broker controls a fixed
Compose project on the host. The backend sees only two read-only bind mounts of
private Unix socket directories; it does **not** receive the host Docker socket.
The broker enforces kernel peer credentials; the worker additionally requires
a workspace-scoped HMAC and keeps credentials sealed under its own UID.

## Operator preparation

1. Provision a **new** random 64-lowercase-hex HMAC seed, confined to
   root-owned mode-0600 `/etc/sigma/deploy.env` as
   `SIGMA_AUTH_POC_RPC_SEED`. Never reuse a local test secret or put it in Git.
2. Set `SIGMA_AUTH_POC_CHECKOUT_ID` to a stable random 32-lowercase-hex ID;
   do not change it between deployments, or the Docker project identity changes.
3. Retain `SIGMA_CLOUD_SPONSORED_ENABLED=true` and its working production
   sponsor. Set `SIGMA_PERSONAL_HOSTED_ENABLED=true` only when Red is ready to
   perform the hosted sign-in acceptance test and has verified provider
   eligibility. Otherwise leave the flag `false`; the existing fallback remains.
4. Deploy a pinned SHA via the normal GCE release manager. It validates the
   standalone worker image, persistent credential mount, broker configuration,
   service health, and the primary application image identities.

## Required acceptance

- Personal enabled **only** when the broker and HMAC are configured, and
  unavailable otherwise; no browser, credentials, or sockets exposed publicly.
- Google member A can connect a real account through SIGMA's same-origin,
  authenticated noVNC viewer. OAuth is completed inside the container, not the
  hosted HTTPS callback. Verify the real account/model catalog before selecting
  Personal. Test one legitimate research request and Paper score.
- Member B cannot start/control member A's browser, see A's account or model
  responses, or reuse A's credentials; concurrent sign-ins reject safely.
- Close browser after connection, keep the encrypted worker record, restart
  backend/worker/broker, and verify previously authorized model inference works
  without a second sign-in.
- Disconnect A, prove both account authorization and per-user state have
  been cleared; B and sponsorship remain unchanged. Any failure remains an
  explicit error, never a silent sponsor fallback.
- Generate a paper and confirm automatic Score. On an injected failure,
  the published PDF stays safe and the activity view shows Score unavailable,
  not Scored. Manual Score must clear the failure.
- Do not promote the release until the actual hosted-provider OAuth and
  inference checks succeed. A working synthetic/local test is insufficient.

## Rollback

The deployment stop path stops both Compose projects and the broker; the
encrypted Personal records remain on the state disk. Reverting to the prior
release leaves the sponsored service unchanged and the Personal feature off.
Do not delete the encrypted records or keys during rollback.
