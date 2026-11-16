# SIGMA low-memory Docker architecture (greenfield POC)

## Intended running services

| Process | Lifecycle | Isolation |
| --- | --- | --- |
| Host Caddy | Always running on GCE | TLS, maintenance, and direct routing |
| SIGMA backend container | Always running | API, sessions, paper generation, project state |
| SIGMA frontend container | Always running | Static UI via internal Nginx |
| One shared Personal ChatGPT container | When enabled | Auth/model worker UID 10001; disposable Chromium UID 11001 |
| Python/Sage research containers | Per experiment | Untrusted code, no network, no model credentials |

There is **no migration** from the earlier experimental per-user Docker pairs.
The shared vault initializes empty. No legacy path, account token, or Docker
project is imported into this implementation.

## Shared Personal ChatGPT (local `./sigma start --prod`)

* `deploy/personal-shared.compose.yaml` defines **one** `personal` service,
  limited to 1792 MiB, with its only ports published on host loopback.
* The credential worker runs as UID 10001, with encrypted per-workspace records
  in `shared-personal-records`. The 32-byte AES-GCM key is created as UID
  10001 in a **different** protected persistent volume,
  `shared-personal-keys`, on first start.
* User identity is derived by SIGMA from its verified Google subject.
  Every model RPC and browser lifecycle operation is authenticated with
  workspace-specific HMAC. No client-provided credential pathname is accepted.
* One Chromium login at a time. A separate browser UID (11001) has no
  read/traversal access to the 0700 credential/key directories.
* A successful account authorization or closed sign-in dialog stops the
  browser process group and removes its temporary profile, without disrupting
  the shared model worker, active research or papers. Abandoned viewers expire.
* The broker revokes **existing** VNC/WebSocket relay connections when a
  browser ends or changes owner; revoking only the listening socket would
  allow an earlier user to view a later user's browser.
* Abandoned OAuth/PKCE attempts are canceled in the original user's encrypted
  storage context. They cannot consume all pending authorization slots.
* Docker SIGTERM triggers graceful worker shutdown rather than waiting for
  SIGKILL. The worker has a bounded grace period; interrupted model operations
  still rely on SIGMA's persisted Stop/Resume semantics.
* `auth-poc/test_shared_runtime.py` exercises two encrypted workspaces,
  invalid HMACs, sequential real Chromium launches, cross-user browser denial,
  browser shutdown and continued account queries without an idle GUI.
  `auth-poc/test_shared_oauth_lifecycle.py` verifies the workspace context of
  cancellations using the real ASGI router. Docker CI also verifies encrypted
  records after graceful worker restart and reports container memory.

At-rest encryption does **not** protect all accounts from a compromise of the
live shared decrypting worker. The POC accepts this explicit tradeoff in return
for low memory, using scoped authorization, strict file permissions and a
separate browser UID. Do not treat it as a production security certification.

## Hosted GCE: remove the redundant Docker edge (opt-in)

Normal production starts with host Caddy forwarding to the Docker edge on
`127.0.0.1:18080`, with unchanged existing routing. Merely merging this
code **does not** switch production traffic or stop its proxy.

The reviewed alternative uses host Caddy directly:

```
HTTPS -> host Caddy -> 127.0.0.1:18081 (backend)
                    -> 127.0.0.1:18082 (frontend)
```

`SIGMA_HOST_DIRECT=true` in `/etc/sigma/deploy.env` activates
`deploy/compose.direct.gce.yaml` and scales Docker `edge` to zero.
Unsetting the flag restores the original edge architecture. Neither mode
publishes the backend or frontend on any non-loopback interface.

### Staged cutover (only after reviewed GCE acceptance)

1. Deploy the code with `SIGMA_HOST_DIRECT` **unset**. Back up the installed
   root-owned `/etc/caddy/Caddyfile`. Production remains on Docker edge.
2. Set `SIGMA_HOST_DIRECT=true`, then bring up only `backend` and
   `frontend` using `deploy/compose-gce.sh up -d --no-build backend frontend`
   while the edge is still running. Verify the new loopback health endpoints,
   and verify both new ports are inaccessible off-VM.
3. Validate `deploy/host-caddy-direct.Caddyfile` with `caddy validate` and
   install it as the host Caddyfile. Reload Caddy. Verify an authenticated
   browser session, API, SSE/streaming, WebSocket and maintenance mode.
4. Restart `sigma.service`. Its startup refuses to scale edge to zero unless
   the **adapted active host Caddy routes for the SIGMA hostname** contain both
   reviewed loopback upstreams and no others. Verify the two
   core application containers are healthy, edge has zero instances, and
   production is serving through host Caddy.
5. Record `docker stats` and VM memory before and after; inspect browser
   memory separately when the temporary Personal GUI is open.

Rollback **without an avoidable outage**: the edge container is scaled to
zero in direct mode. **Do not restore the original Caddyfile first**, because
it would immediately proxy all public requests to a stopped edge.
Instead, while the direct backend/frontend ports are still healthy, unset
`SIGMA_HOST_DIRECT=true` and start/health-check Docker `edge` on
`127.0.0.1:18080` using the same current release. Only after it is healthy,
restore and reload the original host Caddyfile. Confirm public traffic before
reverting the application to an older edge-only release. For a downgrade,
keep the current two loopback endpoints up until Caddy is back on the edge.
The deployment tool refuses direct-mode upgrades/rollbacks if either release
lacks the direct Compose overlay; complete this cutover **before** downgrading.

## Acceptance gates

Do not merge, deploy or call this feature complete until GitHub CI is green
and real sign-in, account selection, inference, Q/A, research, papers,
markdown conversions, Stop/Resume, backend restart, browser close,
cross-user isolation, idle/peak RSS and the host-Caddy rollback are exercised.
The hosted OpenAI plan/OAuth eligibility policy is a separate authorization
gate; local loopback success alone does not establish permission to deploy
hosted Personal ChatGPT.
