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
  no SIGMA source or Docker socket. The container now runs Chromium without
  `--no-sandbox`, using a restricted Docker seccomp profile that allows
  Chromium to create internal user namespaces. It fails closed if the host
  cannot support this sandbox; the remote browser never receives real credentials.
- The browser's `127.0.0.1` points at the worker's listener because of
  Compose `network_mode: service:auth-poc`. The external desktop browser
  receives only a VNC framebuffer, not the OAuth redirect.

## Local SIGMA `start --prod` real sign-in preview

From your normal SIGMA checkout, start Docker Desktop and run:

```sh
./sigma start --prod
```

The standard SIGMA launcher starts the UID-scoped broker and SIGMA's
existing backend and frontend promptly. It prepares architecture-matched,
release-tagged Docker images in a supervised subprocess; the connection
dialog displays preparation progress while Sponsored SIGMA remains usable.
The broker creates private local Unix-socket gateways when needed.
It reconciles orphaned Docker projects labeled for this local checkout after
abnormal exits, and stops the broker and its containers when SIGMA exits or restarts,
without deleting the separate user-scoped authentication state. No companion,
custom startup script, VNC password, or Docker command is required.

Click the SIGMA ChatGPT pill to open a standard dialog with an embedded
**same-origin SIGMA private browser viewer**. OpenAI's login site itself is
displayed inside isolated Chromium, not embedded in an iframe. The standard X
closes the viewer and stops its browser without discarding durable state.
If Docker Desktop is unavailable, SIGMA continues with Sponsored, and does not
silently use pre-existing Mac-local personal tokens.

**Local --prod enables the existing real sign-in preview.** The isolated
browser can open the genuine ChatGPT account chooser, and the user may
authorize a personal account for local-only model requests. A running browser
is not proof of authorization; SIGMA must receive the worker's verified
account binding before switching from Sponsored to Personal.

The prior custom-script `--real-signin-preview` experiment stored account
state in `~/.sigma/personal-signin-preview-state`. Standard `start --prod`
reuses that directory and keeps worker credentials separate from SIGMA.

The provider-eligibility and security review for **hosted multi-user
production** remains a separate gate. No hosted production changes are made
by this local integration PR.

The historical `bash auth-poc/start-sigma-local.sh` only forwards to
`./sigma start --prod` for compatibility and is not a separate launcher.
The old `--real-signin-preview` switch is no longer necessary: local
`start --prod` includes that capability automatically.
A one-time `./sigma setup` may still be required for a new checkout.

Actual macOS Docker Desktop and browser acceptance still require local testing.
CI exercises Linux containers, broker isolation, and the integration contract,
but cannot establish that macOS Docker Desktop works on a particular machine.

## Standalone Docker laboratory (developer diagnostic)


Use a separate worktree on PR #872; from that worktree root with Docker running:

```sh
./auth-poc/start.sh
```

The wrapper builds both images and opens
`http://127.0.0.1:16080/vnc.html` on macOS by default (or the configured
`SIGMA_AUTH_POC_PORT`). Enter the temporary VNC password printed by the
launcher **only to inspect the synthetic local laboratory**. Do **not** sign
into OpenAI, enter any real credentials, or use a personal ChatGPT account.
The account chooser, model discovery, and real inference buttons are disabled;
the worker fails closed with HTTP 403. Synthetic tests exercise the localhost
callback and rejected invalid PKCE state without contacting OpenAI.

The previous one-container implementation allowed Chromium to share a mount
namespace with the credential holder. The new split addresses that flaw.
The earlier isolated CI probe showed Chromium could launch with its internal
sandbox if Docker seccomp did not block namespace syscalls. The current
`auth-poc/chromium-seccomp.json` is based on Microsoft's Playwright
[Docker sandbox profile](https://github.com/microsoft/playwright/blob/main/utils/docker/seccomp_profile.json),
which retains a syscall allowlist and grants the three namespace syscalls
(`clone`, `setns`, `unshare`). This is narrower than disabling seccomp.
The constrained profile must pass CI and the GCE host before this sandbox
work is considered finished. Real OpenAI calls remain disabled regardless.

Stop and retain the test credentials only for controlled restart testing:

```sh
docker compose -f deploy/auth-poc.compose.yaml down
```

To explicitly discard the POC credentials: run `down -v` instead. Do not
use an important account until the adversarial review is accepted.

## User-scoped hosted integration (synthetic only)

The separate, **explicitly opted-in** overlay
`deploy/auth-poc.backend-lab.gce.yaml` mounts only the trusted host broker's
private Unix socket and each user's isolated browser-relay directory into the
SIGMA backend. It does not expose any browser ports, mount the host Docker
socket in SIGMA, activate real OpenAI sign-in, or change sponsored inference.
It is **not included** in ordinary production deployment.

The host broker `auth-poc/host_broker.py` accepts only fixed lifecycle
commands from SIGMA's backend UID. It starts release-pinned, per-user Compose
projects with separate worker token stores, network namespaces and Unix relay
sockets. API handlers resolve the worker ID from the verified Google subject,
not a caller-provided path or account name. The frontend's Personal choice
currently opens only the credential-free lab UI.

CI proves synthetic two-user isolation, routes, sandbox operation, Unix-socket
permissions, and persistence under the private GCE Compose layout. Actual VM
startup, SIGMA reverse-proxy WebSocket behavior, real OpenAI account selection,
verified identity, and per-user inference routing remain **unproven**.

## Production acceptance gates (unmet)

- The basic command-line lab remains single-user. A separately gated hosted
  prototype now binds authenticated Google users to isolated Docker projects;
  credential-free isolation tests pass. Live OAuth, revocation across all
  services, and the real inference routing boundary still require acceptance.
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

## Private Personal inference channel (synthetic milestone)

Each per-user credential worker now creates a **second protected Unix socket**
(`model.sock`) next to `vnc.sock`. SIGMA's backend derives its path solely
from the signed-in Google principal and private workspace mapping. All model
requests contain only a reviewed Responses payload, an opaque 64-character
account binding and a request ID. They never contain a bearer token, OAuth
code, arbitrary URL, headers, or a caller-chosen container path.

The model worker currently replies `disabled` to account discovery and **403**
to every inference request. The routing tests substitute an in-process synthetic
Unix server, demonstrate independent User A/User B results, reject stale account
bindings, reject sponsored-mode access, and verify that no credentials traverse
the backend channel. SIGMA's chat and strategy-provider paths now have a
separate Personal worker branch; the sponsored provider branch and its billing
ledger remain unchanged. A real account is never treated as connected merely
because a browser container is healthy.

For deployment permissions, the two private IPC roots are **mode 0711**
(searchable, not listable), while each user-specific gateway is **mode 0700**
and each socket is **mode 0600** under the dedicated worker/backend UID 10001.
The backend only receives read-only gateway mounts. The broker fails closed if
an IPC root is not mode 0711. These controls are verified on Linux CI, not yet
on macOS Docker Desktop or the actual GCE host.

## Hosted eligibility decision gate

Provider authorization and architecture acceptance are tracked in
[issue #873](https://github.com/bkramerext/sigma/issues/873). Official
[ChatGPT-plan documentation](https://developers.openai.com/siwc/token-sharing-open-source)
asks remotely hosted apps to request access before offering plan usage. This
container-local OAuth lab is neither that approval nor a production design.
