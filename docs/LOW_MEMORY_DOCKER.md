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
`SIGMA_HOST_DIRECT=true` and execute
`deploy/compose-gce.sh up -d --no-build --no-deps edge` **from the active
release checkout**. `--no-deps` is essential: normal `up edge` may recreate
the backend/frontend without their direct port mappings *before* Caddy moves
off those ports. Check Docker `edge` healthy on `127.0.0.1:18080`, then
restore and reload the original host Caddyfile. Finally restart
`sigma.service` to reconcile Compose with the restored edge mode. Confirm
public traffic before reverting to an older edge-only release. For a downgrade,
keep the current two loopback endpoints up until Caddy is back on the edge.
The deployment tool refuses direct-mode upgrades/rollbacks if either release
lacks the direct Compose overlay; complete this cutover **before** downgrading.

## Acceptance sequence: local first, Red deployment afterward

**Acceptance is deliberately split into two local user-facing passes.** Automated
CI and provider-free Docker tests are prerequisites, not substitutes for these
passes. Use the **same reviewed PR #881 SHA** for both passes; if a fix changes
the SHA, rerun affected end-to-end scenarios before passing the gate.

### Gate 1 — normal local SIGMA (no `--prod`)

Run `./sigma start` (without `--prod`) on the user's machine. This is the
baseline local experience and must remain functional independently of the
shared Personal Docker service. Acceptance must cover:

- Startup, login/identity where applicable, normal SIGMA navigation and
  settings, Sponsored/Personal account state as actually offered by this mode.
- Real model requests through research sessions and all enabled strategies,
  paper generation, Q/A, and Markdown conversion (including Current
  Understanding, sessions/strategies and paper fields).
- Streaming/progress reporting, Stop, restart and Resume for sessions and papers,
  with persisted state and no silently successful fallback responses.
- Existing collaboration and user-scope behavior without unexpected prompts,
  blank dialogs or a `--prod`-only dependency.

**Pass means the normal local path is demonstrably healthy.** Do not excuse a
failure as unrelated to the Docker consolidation merely because `--prod`
behaves differently.

### Gate 2 — local production simulation (`--prod`)

Run `./sigma start --prod` **on the same local machine**. This is not a GCE
deployment. Exercise the same SIGMA end-to-end workflows as Gate 1, plus:

- Starts in Sponsored mode when Sponsored is available; no unsolicited personal
  connection prompt. Connect explicitly through the ChatGPT pill.
- Real ChatGPT account chooser/sign-in and loopback OAuth callback, close/cancel,
  disconnect/reconnect, saved account reuse after SIGMA and worker restarts.
  Dialog controls must work repeatedly, including refocusing the login input.
- Confirm **actual Personal** inference for sessions, papers, Q/A and all
  Markdown paths; never silently use Sponsored as a replacement when a Personal
  request fails. Verify streaming, stop and resume across restarts.
- Exactly one shared Personal container with user-bound encrypted records and
  temporary Chromium processes; two-user isolation, one active login browser
  at a time, no idle Chromium/Xvfb/VNC, browser shutdown after closing the
  dialog, and recorded container/VM memory while idle and during login.
- Verify that any unrelated existing SIGMA behavior from Gate 1 remains
  functional with `--prod`.

Only **two passed local gates** authorize preparing the new deployment handoff.
A successful local OAuth loopback does not imply hosted production OAuth or
account/plan eligibility.

### Gate 3 — reset Red's deployment plan and deploy separately

After the two local passes, give Red a **fresh handoff** for the exact accepted
commit SHA and the new low-memory topology. Reset Red's old *deployment plan*,
not the production VM, auth data, or persistent SIGMA state:

1. Treat the earlier per-user-container/browser work as experimental. No
   migration or importing legacy credentials; initialize the shared vault fresh.
2. Retain the host Caddy for TLS/maintenance. Stage direct loopback routing to
   frontend/backend and remove Docker Edge **only after** validating the
   cutover and safe edge-first rollback specified above.
3. Deploy the shared Personal service only after confirming hosted-provider
   eligibility. Preserve the existing healthy Sponsored production route until
   real hosted sign-in/inference are separately authorized and verified.
4. Recheck authenticated routing, API, SSE, WebSockets, all model request paths,
   pause/resume, cross-user isolation and idle/peak memory on GCE. Restore the
   previous known-good release on any failed deployment gate.

**No automatic production deployment or merge is authorized by local tests
alone.** Red's work begins with the accepted SHA and explicit deployment
checks, not the previous deployment assumptions.

### Local `--prod` Personal ChatGPT diagnostics

If the Connect to ChatGPT dialog cannot open its embedded Chromium browser,
click **Copy diagnostics** on the error state and paste the copied report to
the developer. You do not need to interpret Docker logs or collect a series
of incremental screenshots.

Each local `--prod` launch creates a private mode-0600 diagnostic log at
`~/.sigma/personal-shared-poc/diagnostics/personal-<date>-<random>.log`.
SIGMA prints the exact location in its starting terminal. The log follows
the launch, image reconciliation, Docker Compose, Unix broker authentication,
worker RPC and browser-start requests, with the same 12-digit hexadecimal
attempt identifier shown in the error dialog. It records fixed stage/reason
codes, HTTP status, elapsed time and selected architecture, **not** tokens,
cookies, account identities, workspace IDs, browser contents or raw Docker
stderr. Old logs are retained only for a bounded set of recent launches.

The Copy action is available only for an authenticated user on the local
`--prod` server; it returns a bounded, filtered excerpt. If copying fails,
paste the `SIGMA_PERSONAL_DIAG` lines from the terminal or the private log.
Do not attach unredacted Docker/browser logs containing sign-in details.
This facility is for POC acceptance diagnostics and does not enable hosted
Personal ChatGPT.
