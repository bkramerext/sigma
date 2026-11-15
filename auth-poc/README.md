# Portable, containerized Personal ChatGPT OAuth experiment

**Status: local technical POC, NOT production-authorized or deployable to end users.**
The image demonstrates the same loopback OAuth logic in a Linux/amd64 container,
with both Chromium and SIGMA's temporary callback listener in the same network
namespace. The Mac browser only displays a remote framebuffer using noVNC.
The outer browser never receives the OpenAI OAuth redirect.

## Run on a Mac with Docker Desktop

From the SIGMA repository root, with Docker Desktop running:

```sh
./auth-poc/start.sh
```

This builds and launches the same Linux/amd64 image used by the cloud deployment
POC, prints the per-container VNC password, and opens the browser-viewing page on
macOS. Enter that password, then in the **remote** Chromium window click
**Open ChatGPT account chooser**, complete OpenAI sign-in, and click
**Verify Personal model access**.

Stop:

```sh
docker compose -f deploy/auth-poc.compose.yaml down
```

This deliberately leaves the named volume with private credentials, to test
restart/refresh. To delete that POC-only data, explicitly use `down -v`.

## Production portability requirements

- The same Linux/amd64 Dockerfile, image dependencies, and loopback callback
  run inside the Google Cloud VM. There is **no macOS localhost callback** and
  no `uv run` or app installation for an end user.
- NoVNC is bound ONLY to host `127.0.0.1:16080` and is unencrypted.
  Its VNC stream is guarded by a random password kept in private container
  tmpfs, but it does not have a per-user Google identity. **NEVER reverse-proxy or publish it to the Internet as-is.**
  Per-user Google-identity-gated browser streaming, browser-session isolation,
  cookie protections, and lifecycle/cleanup are required before hosted use.
- Chromium's nested Linux namespace sandbox cannot start under the POC's
  default Docker seccomp and `no-new-privileges` policy. The POC uses
  `--no-sandbox` **inside a non-root, capability-dropped, read-only Docker
  container**. This is a laboratory-only security trade-off. Production
  needs a reviewed Chromium sandbox policy before any real multi-user rollout.
- The existing rootless research execution daemon uses `--network=none`.
  This authentication image deliberately needs outbound TLS and must never
  share the research executor's capability boundary.
- The current Compose file is a portable local profile, not yet integrated into
  SIGMA's pinned GCE image builder, state backup, or rollout service. Those are
  explicit remaining acceptance gates, not manual production steps.
- A technically successful login does NOT establish that OpenAI allows an
  interactive browser inside a multi-user hosted service to use the OSS client.
  Do not enable in public SIGMA without resolving provider eligibility.

## What constitutes a successful *local* technical POC?

The OpenAI chooser appears in the container-owned Chromium window, its
`127.0.0.1` callback reaches SIGMA's listener inside the container, and
`Verify Personal model access` returns connected. Docker image restarts
must not require any hand-created dependencies.

This POC does not claim remote-browser production integration, model inference,
or an OpenAI-approved hosted OAuth flow. It deliberately does not alter the
existing production sign-in pill or cloud authentication policy.
