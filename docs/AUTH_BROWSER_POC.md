# Containerized Personal ChatGPT OAuth proof of concept

Status: **experiment only**. Not an approved hosted OpenAI connection, not
multi-user-capable, and not enabled for ordinary SIGMA research.

## Hypothesis

OpenAI's existing open-source OAuth registration accepts a callback to
`http://127.0.0.1:<ephemeral>/auth/callback` when **Chromium and the SIGMA
listener run in the same Docker container**. The user's browser only views and
controls that Chromium through SIGMA's authenticated website.

This differs from the rejected public HTTPS callback and does not require a
desktop-installed companion.

## Architecture and security boundary

- The same image is built locally and on the VM:
  `auth-browser-poc/Dockerfile`, based on the exact SIGMA backend release image.
- Inside the container: Xvfb, Chromium, SIGMA's unmodified `chatgpt_auth.begin`
  and localhost callback listener, then one test model call.
- SIGMA's admin-only `/api/auth-browser-poc/*` endpoints forward control and
  screenshots to an internal HTTP worker using a private shared key. The
  cloud service has **no published port**. The local worker is bound to
  `127.0.0.1:18765` only. Ordinary users cannot invoke the experiment.
- The worker's ChatGPT credential store is isolated in its own Docker
  volume locally and a separate directory on SIGMA's persistent GCE state
  disk in production; it is never the sponsor account store or a research
  project. The backend does not
  import those credentials.
- The viewer is deliberately rudimentary (PNG snapshots and keyboard/mouse
  forwarding) to avoid a publicly reachable VNC or WebSocket service.
- **Trust warning:** The SIGMA backend relays screenshots and keystrokes,
  including any credentials entered during sign-in. This approach must not be
  offered to ordinary hosted users without a dedicated security review.
  Chromium currently uses `--no-sandbox` inside a restricted Docker container;
  that, too, must be addressed before production.
- OpenAI documentation has *not* established that this arrangement is
  authorized for a shared hosted service. Technical OAuth success would not
  establish eligibility.

## Local experiment

On the POC commit, run the existing SIGMA launcher (Docker Desktop must be
running):

```bash
launch <POC_COMMIT_SHA> --prod --signin --navigate
```

The launcher builds the **same** backend and browser images used by the cloud
release builder, creates a private experiment key, and starts the container.
There is no second terminal command, `uv run`, or desktop companion.

Sign into SIGMA as its local administrator. Open:

`http://127.0.0.1:5173/api/auth-browser-poc/ui`

Click **Open OpenAI chooser in container**. Interact with the remote Chromium
image. When it shows **connected**, click **Send one real test turn**. A
successful response verifies the localhost callback, token exchange, token
storage, and a genuine model request inside the container.

The test requires you to enter/sign into your OpenAI account. This has
**not** been tested against a real OpenAI login in CI.

## Reproducible cloud deployment

On an **explicitly approved experimental deployment**, set
`SIGMA_AUTH_BROWSER_POC_ENABLED=true` once in the protected
`/etc/sigma/deploy.env`. The existing unattended release deployer then:

1. Builds the normal SIGMA backend/frontend images plus the browser image
   from the exact release Git SHA.
2. Starts the opt-in `deploy/compose.auth-browser-poc.yaml` service using
   the existing `deploy/start-gce.sh` route.
3. Creates an owner-restricted key automatically under the persistent SIGMA
   state disk, mounts it in the backend and browser containers, and keeps the
   browser service off public ports.
4. Checks container health and verifies that the browser image has the same
   pinned source commit as the rest of SIGMA.

The user reaches the **same** `/api/auth-browser-poc/ui` path on the hosted
SIGMA website, through the normal Google-authenticated API. No local laptop
listener or application is involved.

**Default remains off; this branch is not a production rollout.**

## Exit criteria

- Docker image builds and its display, status and control endpoints work on a
  developer Mac with the normal Docker installation.
- Real OpenAI account chooser works *inside the container*, with OAuth
  redirect to that container's loopback listener and a real one-turn inference.
- Same image and container execution work when deployed through the release
  automation, with no additional user machine or manual VM shell steps.
- Security assessment of remotely relayed login credentials, browser sandbox,
  multi-user isolation, and OpenAI's support/authorization conditions.

The POC intentionally does **not** route SIGMA research to the worker yet;
that would require a subject-bound durable multi-user credential and inference
architecture after feasibility and eligibility have been established.
