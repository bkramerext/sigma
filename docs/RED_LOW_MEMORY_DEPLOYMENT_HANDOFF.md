# Red deployment handoff — SIGMA consolidated low-memory architecture

**Prepared:** 2026-11-16. **Source:** PR #881, the commit containing the
`SIGMA_PERSONAL_DIAGNOSTICS_ENABLED` default-off switch after both local
acceptance passes. **Do not deploy an unmerged feature branch.** Choose the
exact merged 40-character release SHA only after verifying its tree includes
PR #879's restored Markdown/paper fixes and all of PR #881.

## Accepted versus not accepted

- **Accepted locally by the user:** normal `./sigma start` and the local
  `./sigma start --prod` Personal ChatGPT connection through the iframe
  into the **single** shared Docker Chromium service. Native macOS peer
  authorization now uses OS-reported `getpeereid(2)`; no UID bypass.
- **Passed CI before deployment:** Linux AMD64/ARM64 container runtime,
  native macOS AF_UNIX peer UID authorization, frontend, Ruff, SIGMA,
  browser, project storage/types. Confirm these on the final merged SHA.
- **Not accepted on GCE:** host-Caddy direct cutover, rollback, and actual
  VM idle/peak memory.
- **Not authorized by local acceptance:** hosted Personal ChatGPT OAuth,
  plan-based inference, or copying local ChatGPT tokens to the VM. SIGMA's
  hosted Personal credential path remains explicitly unavailable.
- **Verbose diagnostics:** `SIGMA_PERSONAL_DIAGNOSTICS_ENABLED=1` is a
  local-only opt-in, default **off**. Do not add it to
  `/etc/sigma/deploy.env` or production Compose environment.

## Architecture and scope

Current deployed baseline:
`HTTPS -> host Caddy -> Docker edge (127.0.0.1:18080) -> frontend/backend`.

First production topology target:
`HTTPS -> host Caddy -> backend (127.0.0.1:18081)` for `/api*`,
and `HTTPS -> host Caddy -> frontend (127.0.0.1:18082)` for everything
else. **Two** application containers run persistently; Docker edge is scaled
to zero.

The **third persistent shared Personal ChatGPT container** is in the accepted
*local* POC topology, but is **not yet wired for hosted use**. Do not deploy
or enable it on GCE before provider authorization and a reviewed hosted
credential/connection design. This is an intentional two-stage rollout, not
a covert fallback to synthetic lab accounts or per-user containers.

No migration of experimental Personal credentials. No resetting Google
identities, projects, research sessions, papers, accounting records, sponsor
credentials or the existing state disk.

## Stage A — review and routine guarded release, keeping existing Docker edge

1. Establish actual production baseline by **read-only** host inspection.
   Record the current release pin, host Caddyfile, `sigma.service`, container
   image IDs, backed-up state integrity, and idle/peak memory. Observe
   configured provider: preserve Sponsored `chatgpt` and current allowance
   settings. Do not infer current VM state solely from archived runbooks.
2. Confirm all final-sha CI checks, code/schema compatibility, and a fresh
   *application-consistent* verified recovery copy. Follow
   `docs/DEPLOYMENT_RUNBOOK.md` and `docs/OPERATION_RUNBOOK.md`, including
   preflight; do not assert backup/schema flags without evidence.
3. Ensure `SIGMA_HOST_DIRECT` is **unset or false** and
   `SIGMA_AUTH_POC_LAB_ENABLED` stays false. Do not modify sponsor or OAuth
   settings. Back up the root-owned active Caddyfile securely.
4. Deploy the exact approved, merged release SHA via the guarded helper:

   ```sh
   sudo python3 /opt/sigma/current/deploy/deploy-gce-release.py FULL_40_CHARACTER_SHA \
     --backup-verified --schema-compatible
   ```

   Use these flags **only if** Red's actual backup and compatibility checks
   justify them. Confirm the protected release pin, images, backend/frontend/
   edge health, public HTTPS, hosted Google auth, sponsored connection state,
   API/SSE/WebSocket paths, maintenance OFF, and unchanged persistent state.
   Stop before Stage B on failure.

## Stage B — separately validate host Caddy direct routing

1. Use only the reviewed `deploy/compose.direct.gce.yaml` overlay; stage
   `SIGMA_HOST_DIRECT=true` in the root-owned, mode-0600
   `/etc/sigma/deploy.env` with a secure previous copy. Before Caddy
   changes, start **only** backend/frontend using the updated release:

   ```sh
   deploy/compose-gce.sh up -d --no-build backend frontend
   ```

   Confirm healthy `127.0.0.1:18081` and `:18082` and no non-loopback
   publication. Keep the old Docker edge running at `:18080`.
2. Compare the active Caddy host site's TLS, compression, security headers,
   maintenance import, `/api` and `/api/*` routing with
   `deploy/host-caddy-direct.Caddyfile`; preserve any live site-specific
   settings. Validate and adapt the proposed file with the installed Caddy
   version **before** replacing the root-owned active config. Reload host
   Caddy. Probe authenticated UI/API, streaming/SSE, WebSockets, Google
   identity, and maintenance behavior.
3. Restart `sigma.service`. `deploy/start-gce.sh` requires the active
   host Caddy JSON to match the reviewed direct upstreams before it can scale
   Docker edge to zero. Refuse any need to bypass that guard.
4. Verify edge has **zero** running containers, frontend and backend remain
   healthy, API/frontend port bindings remain loopback-only, HTTPS works from
   an external browser, and authenticated research/papers/Q&A/Markdown/Resume
   behave as expected. Measure actual VM and container idle/peak memory and
   compare to Stage A. Record all observations.

### Critical rollback order — do not cause avoidable downtime

If direct mode fails, while the backend/frontend direct loopback ports are
still live:

1. Remove `SIGMA_HOST_DIRECT=true` from the protected env (or set false).
2. **Start Docker edge first**, without dependency recreation:

   ```sh
   deploy/compose-gce.sh up -d --no-build --no-deps edge
   ```

3. Confirm Docker edge is healthy on `127.0.0.1:18080`.
4. Only **then** restore and reload the previous host Caddyfile.
5. Restart `sigma.service`, verify public HTTPS, auth, streaming, projects,
   paper/job/accounting persistence and maintenance OFF.

Never restore the old host Caddyfile while Docker edge is still scaled to
zero. The release helper refuses an automatic downgrade across incompatible
direct Compose overlays; undo the proxy cutover safely before considering an
older release. Code rollback does not undo state/schema changes.

## Stage C — hosted Personal ChatGPT (explicitly deferred)

Do not interpret working macOS loopback OAuth as permission to use the same
sign-in flow remotely on GCE. Verify OpenAI's supported remotely hosted
authentication and inference entitlement **before** implementing or starting
the shared Personal worker in production. Do not substitute local credentials,
a synthetic authorization lab, Sponsored tokens, or a deceptive sign-in.
When a supported path exists, perform a fresh design/security review for
multi-user credential storage, authentication, Docker privilege, hosted relay,
server-side sessions and consent; retain one shared worker rather than
reintroducing per-user container pairs. Test with authorized users and
revalidate each SIGMA model request path.

## Required report back to the owner

Report the **merged source SHA**, deployed SHA, exact Stage A/B status, host
Caddy version, preflight and backup integrity outcomes, running container
counts and health, release pin/image IDs, authenticated public probes,
staged/rolled-back state, and *measured* VM/containers memory. Explicitly say
whether Personal ChatGPT hosted access is still blocked. Do not claim success
from a local run or mock-only provider test.

Production deployment remains a Red/operator action; writing this handoff
does not change the GCE VM or authorize credentials/spending modifications.
