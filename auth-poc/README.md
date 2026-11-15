# SIGMA containerized Personal ChatGPT authentication experiment

**Not production-authorized. Do not expose this lab to the public Internet.**
This experiment specifically tests OpenAI's documented loopback callback with
a browser that actually runs inside Linux on a remote-capable Docker host.

## Portable architecture

Two independent Linux/amd64 containers have different UIDs, PID namespaces
and mount namespaces, but deliberately share a Docker network namespace:

- **auth-poc worker**: FastAPI, SIGMA's existing PKCE/OIDC/token validation and
  protected, persistent `auth-poc-state` volume. Its HTTP service binds
  `127.0.0.1:8001` within the shared namespace. No Chromium installed.
- **browser**: Chromium, Xvfb, x11vnc and noVNC. It has *no auth volume* and
  no SIGMA source or Docker socket. Chromium's own namespace sandbox cannot
  start under the tested Docker restrictions; its browser-only container
  currently uses `--no-sandbox` solely for synthetic startup verification.
- The browser's `127.0.0.1` points at the worker's listener because of
  Compose `network_mode: service:auth-poc`. The external desktop browser
  receives only a VNC framebuffer, not the OAuth redirect.

## Local reproduction

Use a separate worktree on PR #872; from that worktree root with Docker running:

```sh
./auth-poc/start.sh
```

The wrapper builds both images and opens
`http://127.0.0.1:16080/vnc.html` on macOS. Enter the temporary VNC password
printed by the launcher, then use **the remote Chromium** to open OpenAI's
account chooser. The **Verify model catalog** button checks the authorized
account's models; **Test one real model response** performs a bounded
Responses API request.

The previous one-container implementation allowed Chromium to share a mount
namespace with the credential holder. The new split fixes that specific flaw,
but Chromium's own sandbox still requires a production-safe solution. The
server refuses all real OpenAI calls while that work is unresolved.

Stop and retain the test credentials only for controlled restart testing:

```sh
docker compose -f deploy/auth-poc.compose.yaml down
```

To explicitly discard the POC credentials: run `down -v` instead. Do not
use an important account until the adversarial review is accepted.

## Production acceptance gates (unmet)

- The current lab is **single-user**, though CI also checks two independently
  named Compose stacks have distinct credential volumes. Google identity must bind a unique worker
  and browser session per SIGMA user, including lifecycle and revocation.
- noVNC is visible only on the host loopback, using HTTP plus a temporary
  VNC password. A hosted integration must provide TLS and a Google-session
  checked, user-specific browser stream through SIGMA's backend, without
  publishing noVNC or relying on a password in a terminal.
- The same images are now available to SIGMA's **opt-in GCE synthetic lab**:
  `SIGMA_AUTH_POC_LAB_ENABLED=true` makes the hands-off release builder attest
  both images from the exact commit, starts them with no publicly exposed VNC
  port, verifies health and image identity, and binds the isolated credential
  volume to `/srv/sigma-state/auth/auth-poc`, covered by normal disk snapshots.
  Default is `false`. This does **not** expose a Personal ChatGPT connection
  to hosted users: the OAuth endpoints remain denied.
- Local Docker Desktop vs. GCE Docker, macOS/ARM emulation, browser lifecycle,
  multiuser concurrency, and actual model generation still require relevant
  tests. The image's Debian browser packages are currently not snapshot-pinned.
- OpenAI documents the OSS SIWC flow for locally hosted and self-hosted apps
  and directs developers interested in remotely hosted apps to its interest
  form. Passing localhost OAuth in a container does NOT establish that this
  arrangement is authorized for SIGMA's multi-user hosted service.
- The lab guard `SIGMA_AUTH_POC_LAB=1` must not become a production bypass.
  Production must fail closed until all previous gates are resolved.
