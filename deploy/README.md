# T22 cloud deployment preparation

SIGMA's current cloud app uses SQLite for Google access/session state and POSIX
files for each private workspace. The deployment therefore runs its FastAPI
backend as an unprivileged container on a host with a durable, private mounted
volume. A Cloudflare Worker serves the built Vite app over HTTPS and proxies
`/api/*` to a remotely managed Cloudflare Tunnel hostname protected by a
Cloudflare Access Service Auth policy. Only the Worker holds the service token.
The origin has no public listener; the host maps the API to loopback. Set the
Tunnel's HTTP Host Header to the public app hostname so FastAPI's trusted-host
and exact-origin checks see the configured SIGMA origin. The curated Demo JSON
stays in the versioned image at `/app/cloud-demo` and is validated to resolve
outside private storage at startup.

This is an operations-ready hybrid design, not an assertion that Cloudflare
Containers, D1, or R2 can directly replace current app storage. Cloudflare
container disks are ephemeral unless an external persistence layer is used;
SIGMA's existing filesystem and SQLite code is preserved on a durable host
volume. This branch does not build or publish public infrastructure.

Current Cloudflare pricing documentation lists the Workers Free plan at
100,000 requests/day and 10ms CPU per invocation; static asset requests are
currently free. The Workers Paid plan has a $5/month account minimum with
included usage and metered overages. This Worker design may run on Free at low
traffic, but actual API request volume/CPU must be measured before selecting a
plan. Those figures exclude the required durable Linux host, disk, encrypted
backups, any custom-domain registration, and provider inference. See
[Cloudflare Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/).

## Prerequisites and secrets

- A Cloudflare account and verified zone for the Worker custom hostname, a
  remotely managed Tunnel to the host, and an Access application/policy for the
  origin hostname. The policy must accept only the Worker service token.
- Google OAuth Web application credentials. Add the exact redirect URI
  `https://<public-host>/api/cloud-auth/callback`; set the Google authorized
  origin to the same host. Google client ID/secret, bootstrap administrator
  email, and administrator contact email are required.
- A Linux host with Docker Engine, `python3`, `npm`, outbound access to pull the
  pinned base image, and a durable filesystem with enough capacity for private
  research artifacts and backups. Pin the installed `cloudflared` version per
  the pinned image in `deploy/run-tunnel.sh`; its token belongs in a
  root-managed group-readable file only.
- Install `age` on backup and recovery hosts if using the documented encrypted
  archive procedure; keep its private identity outside the live host.
- Node/npm to build and deploy; Wrangler 4.152.0 is pinned in this repository.
  Cloudflare account credentials are used by Wrangler only at deployment time.
  Authenticate Wrangler interactively with `wrangler login` or provide a
  scoped Cloudflare API token in the operator's environment. Limit the token
  to deploying this Worker and managing its assets/secrets; do not store it in
  this checkout or pass it on the command line.

Copy example files to a protected path outside the checkout and fill every
placeholder. Runtime env files and Worker secret files must be mode `0600` and
must never be committed. Do not put secrets in Worker vars, frontend Vite
variables, build args, image layers, shell command arguments, or debug logs.
The origin service token ID and secret are installed as Worker secrets with
the one deployment command below. Never enable Uvicorn access logs: callback
URLs contain short-lived OAuth codes and state.

## First deployment

From the repository root on the Linux host, create `/etc/sigma` files and the
durable volume. Example paths below are replaceable, but keep the data root
separate from the application checkout and backups:

```sh
install -d -m 0700 "$HOME/.config/sigma"
install -m 0600 deploy/runtime.env.example "$HOME/.config/sigma/runtime.env"
${EDITOR:-vi} "$HOME/.config/sigma/runtime.env"
sudo deploy/install-volume.sh /srv/sigma/data
sudo deploy/build-api.sh sigma-api:2026-10-23-a1b2c3d
sudo deploy/run-api.sh /srv/sigma/data "$HOME/.config/sigma/runtime.env" sigma-api:2026-10-23-a1b2c3d
```

Create a service token and save the four Worker values from
`deploy/cloudflare/worker-secrets.example.json` to a mode-0600 file outside
the repository. The API origin must be the HTTPS Access-protected Tunnel
hostname, distinct from the public app origin.

```sh
install -m 0600 /dev/null "$HOME/.config/sigma/worker-secrets.json"
${EDITOR:-vi} "$HOME/.config/sigma/worker-secrets.json"
SIGMA_WORKER_SECRETS_FILE="$HOME/.config/sigma/worker-secrets.json" deploy/deploy-worker.sh
```

In Cloudflare, attach the Worker to the exact `SIGMA_PUBLIC_ORIGIN` hostname.
Configure the Tunnel origin route and its HTTP Host Header to that hostname,
then apply Access Service Auth to the origin host. Restrict it to the exact
service token installed above. Configure browser Google login against the
public Worker hostname, never the origin hostname.

Put the tunnel token in a root-managed file owned by uid 0/group 65532, mode
0640, then run:

```sh
sudo install -o root -g 65532 -m 0640 /dev/null /etc/sigma/tunnel-token
sudoedit /etc/sigma/tunnel-token
sudo chown root:65532 /etc/sigma/tunnel-token
sudo chmod 0640 /etc/sigma/tunnel-token
sudo deploy/run-tunnel.sh /etc/sigma/tunnel-token
```

The pinned cloudflared container shares host networking to reach the API's
loopback-only port. The token is read-only mounted and not passed as a process
argument or printed.

Validate without signing in:

```sh
curl --fail --show-error https://sigma.example.org/healthz
curl --fail --show-error https://sigma.example.org/api/cloud-demo/ > /tmp/sigma-demo.json
curl -i https://sigma.example.org/api/projects/recent  # expected 401
docker inspect --format '{{.State.Health.Status}}' sigma-api
```

`/healthz` exposes only ready/not-ready. The API container has no Linux
capabilities, cannot gain privileges, has a read-only root filesystem, and
is limited to 256 processes. The private API must return 401
without a session. Do not test with real model providers during deployment.

## Updates and rollback

Build every backend image with a unique source revision tag; preserve the
previous image locally until the new version passes `/healthz` and the browser
smoke. The image starts with a fail-closed volume marker/config check and never
creates that marker itself.

```sh
sudo deploy/stop-api.sh
sudo deploy/run-api.sh /srv/sigma/data "$HOME/.config/sigma/runtime.env" sigma-api:2026-10-23-d4e5f6a
# On failure, rerun run-api.sh with the previous immutable image tag.
SIGMA_WORKER_SECRETS_FILE=/etc/sigma/worker-secrets.json deploy/deploy-worker.sh
# Worker rollback: deploy/rollback-worker.sh PREVIOUS_VERSION_ID
```

Backend rollback reuses the same persistent volume and replaces only the
container. Worker rollback uses Cloudflare's deployment version ID. Keep the
app and API revisions compatible until each has passed health and Demo checks.
Do not delete old images or backups until recovery has been verified.

## Backup and restore

Stop-the-world backups include SQLite state, workspace data, projects,
sessions, and artifacts. They do not include the separately versioned public
Demo snapshot. The script stops `sigma-api`, archives only regular files and
directories, writes a mode-0600 archive, and restarts the container on exit.
Keep backups outside the data root and encrypt them before copying off-host.
Restrict backup access as strictly as live workspace access. A host-level
encrypted backup target or an approved encrypted backup service is a required
operator prerequisite; this repository does not configure a billable storage
service or hold its credentials. One reproducible option is `age`: keep the
recipient private key away from the backup host and make its public recipient
available to the operator.

```sh
sudo install -d -o root -g root -m 0700 /srv/sigma-backups
sudo deploy/backup.sh /srv/sigma/data /srv/sigma-backups/sigma-$(date -u +%Y%m%dT%H%M%SZ).tar.gz
AGE_RECIPIENT='age1replace-with-approved-public-recipient'
archive=/srv/sigma-backups/sigma-20261023T000000Z.tar.gz
sudo age -r "$AGE_RECIPIENT" -o "${archive}.age" "$archive"
sudo chmod 0600 "${archive}.age"
```

For restore, stop the API, initialize a **new empty** volume, restore the
archive, and validate it before pointing the container at it. Never restore
over the current data root. Example, as root on the host:

```sh
sudo install -d -o root -g root -m 0700 /srv/sigma-restore
sudo age -d -i /etc/sigma/backup-identity.age -o /srv/sigma-restore/backup.tar.gz /srv/sigma-backups/sigma-20261023T000000Z.tar.gz.age
sudo chmod 0600 /srv/sigma-restore/backup.tar.gz
sudo docker stop sigma-api
sudo install -d -o 10001 -g 10001 -m 0700 /srv/sigma/data-restored
sudo python3 ops/data_archive.py restore /srv/sigma-restore/backup.tar.gz /srv/sigma/data-restored --uid 10001 --gid 10001
sudo install -o 10001 -g 10001 -m 0600 /dev/null /srv/sigma/data-restored/.sigma-deployment-volume-v1
sudo sh -c "printf 'SIGMA durable cloud data volume v1\\n' > /srv/sigma/data-restored/.sigma-deployment-volume-v1"
sudo chown 10001:10001 /srv/sigma/data-restored/.sigma-deployment-volume-v1
sudo docker rm sigma-api
  sudo deploy/run-api.sh /srv/sigma/data-restored "$HOME/.config/sigma/runtime.env" sigma-api:2026-10-22-cafe123
curl --fail https://sigma.example.org/healthz
```

Before a production restore, verify the archive source, decrypt it into a
restricted location, preserve the original data root, and inspect application
health and representative account/project records before reopening traffic.

## Local verification

No Cloudflare or Google account is needed for deterministic checks. The
repository test suite includes worker routing, fail-closed startup/config,
private volume, and archive/restore tests. A live local stack can be run with
the procedure in `messages/t22_deployment_r4r.txt`; it uses deterministic
placeholder OIDC settings and the checked-in Demo, makes no Google or model
calls, and tests the real browser-to-Worker-to-API path. Local SIGMA continues
to run without cloud configuration; production checks are only enabled by the
container entrypoint and `SIGMA_CLOUD_AUTH_ENABLED=true`.

Cloudflare documentation notes that container filesystems are ephemeral by
default; see [Container FAQ](https://developers.cloudflare.com/containers/faq/).
Worker static assets can be routed through the Worker before the SPA fallback;
see [Static Assets](https://developers.cloudflare.com/workers/static-assets/).
