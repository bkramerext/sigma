# SIGMA on Google Cloud Compute Engine

This is a reviewed deployment package, not permission to create resources. The
only hosting target in this plan is one Linux Compute Engine VM in Oregon
(`us-west1`), with a dedicated persistent state disk. No resource creation,
billing activation, live Google OAuth exchange, or OpenAI request was performed
for this readiness work.

## Package and runtime shape

`Dockerfile` builds the Python 3.12 FastAPI service from `uv.lock`; the
`deploy/frontend.Dockerfile` builds the SPA from `package-lock.json` and serves
the static bundle with Nginx; `deploy/compose.yaml` runs these with Caddy as the
HTTPS edge. Python version and Docker CLI, uv, Node, Nginx, and Caddy base images
are fixed to amd64 digests. The lockfiles pin Python/JavaScript packages. Build
the Python and Sage execution images from the existing `sandbox-poc` recipes
and tags in `src/sigma/python_sandbox.py`; SIGMA continues to apply its existing
no-network, non-root, memory, CPU, process, wall-time, and output limits.

The web/API container is unprivileged, has a read-only root filesystem, drops
Linux capabilities, and sees only a **separate rootless Docker daemon** for
research execution. Do not mount `/var/run/docker.sock` or any rootful Docker
socket into the app. The rootless sandbox daemon runs under the dedicated
`sigma-sandbox` Linux account, which has no access to SIGMA's state disk. Its
socket group is shared read/write with the backend container so the existing
executor can create bounded runner containers. Generated code itself receives
no daemon socket and no SIGMA data mounts. This daemon boundary is still an
operator security acceptance item: verify on the target Linux image that a
compromised rootless runner cannot read the app state or gain host root before
inviting users.

Compose exposes only the Caddy edge on TCP 80/443 (UDP 443 is optional HTTP/3).
The backend and frontend have no host-published ports. Caddy serves SPA routes
and proxies `/api/*` to FastAPI on the same origin. Caddy stores certificates in
its named `/data` volume and obtains/renews them after the DNS record points to
the VM and inbound TCP 80/443 are reachable. Google OAuth's production origin
is always `https://$SIGMA_DOMAIN`; its exact callback is
`https://$SIGMA_DOMAIN/api/cloud-auth/callback`.

All private hosted state uses `$SIGMA_STATE_DISK_MOUNT/auth` on the attached
state disk: Google auth/session SQLite, subject/workspace mappings, user project
trees and Recent state, computational artifacts, and the cloud-research
reservation/accounting ledger. Compose's GCE override binds that directory into
the container. The reviewed public Demo audit is copied read-only into the app
image; it is not placed on or derived from user workspaces.

Cloud auth is explicitly set to `true`, and the shared OpenAI credential is
provided only through a mounted file. `config_secrets.secret_value()` accepts
either the existing direct environment setting or a `*_FILE` path; if both are
set, the file is not a fallback and the configuration fails closed. The health
check verifies Google auth config, presence of the sponsored service credential,
and valid user/global spending ceilings without making any outbound request.
The deployment does not set `SIGMA_CLOUD_AUTH_LOCAL`, so its hosted auth status
must report `target: hosted`. T43's explicit local Google mode remains limited
to loopback HTTP and retains its separate local ChatGPT flow; the hosted
middleware blocks `/api/ai/*` after Google identity authorization. The package
test asserts Compose does not enable local mode, the local deployment smoke
asserts `target: hosted`, and `tests/cloud_auth.py` covers both local and hosted
routes.
Cloud workspace isolation, per-user/global USD reservations, token/concurrency
limits, no-replay handling for unknown provider outcomes, and the sponsored
inference route remain the existing T22/T41 services. Personal ChatGPT/API
credentials are not forwarded to the container. OpenAI usage is a separate
external bill and is not covered by Google's trial credit.

## Initial sizing

Candidate for a small invited pilot, pending measurement: `e2-standard-4`
(4 vCPU, 16 GiB), a 100 GiB standard boot disk, and a 200 GiB balanced state
disk in one `us-west1` zone. Keep hosted research concurrency at one while Sage
and multi-user memory profiles are measured. Sage's 1 GiB execution limit is
per runner; its Docker image is several GB and will take substantial time and
disk during the first build. A 16 GiB VM and 100 GiB boot disk are a candidate,
not evidence that building or concurrent Sage jobs meet production latency or
memory targets. The one-day readiness goal does not establish availability,
capacity, RTO/RPO, or a public-alpha approval.

## Cost estimate

List-price estimate prepared 2026-10-23, USD, before negotiated discounts/tax.
Use 730 hours for a normalized month and 2,160 hours for 90 days. E2 prices are
regional and the VM number is a candidate planning rate; reconfirm exact
`us-west1` price, free-tier eligibility, trial eligibility, tax, and SKUs in the
Google Cloud Pricing Calculator before approval. Disk and snapshot rates are
prorated by time. Snapshot size is compressed/changed data, so the 100 GiB is a
budget allowance, not its provisioned disk size.

| Google Cloud line item | Assumption and rate | Normalized month | 90 days |
| --- | --- | ---: | ---: |
| Compute Engine `e2-standard-4` | 4 vCPU, 16 GiB, 730/2,160 h at about $0.13402284/h | $97.84 | $289.49 |
| Boot Persistent Disk | 100 GiB standard, about $0.0000548/GiB-h | $4.00 | $11.84 |
| State Persistent Disk | 200 GiB balanced, about $0.00013699/GiB-h | $20.00 | $59.18 |
| VM external IPv4 | One in-use standard-VM address at $0.005/h | $3.65 | $10.80 |
| Regional standard snapshots | Budget 100 GiB stored at $0.000068493/GiB-h | $5.00 | $14.79 |
| Cloud Storage backup copy | 50 GiB single-region Standard at $0.02/GiB-month | $1.00 | $3.00 |
| Internet egress | 10 GiB/month to North America; first 1 GiB/month free, then $0.12/GiB | $1.08 | $3.24 |
| Cloud DNS | One managed zone (~$0.20/mo) and 500k queries (~$0.20/mo) | $0.40 | $1.20 |
| Secret Manager | Two active versions and low-volume reads within current free limits | $0.00 | $0.00 |
| Cloud Logging | Not enabled; Docker local log rotation, no GCP ingest | $0.00 | $0.00 |
| **Estimated total** | Domain registration and OpenAI API usage excluded | **$132.97** | **$393.54** |

At this deliberately always-on estimate, the $300 trial credit would be used up
around day 69 of a 90-day trial. The remaining 21 days are about $93.54 of usage with no
trial credit available; under Google's current trial rules resources stop when
the credit is exhausted or 90 days elapse if the account is not upgraded. Do not
assume unused time or free-tier eligibility offsets this bill. An existing
domain/registrar is assumed; domain purchase or renewal is additional and
requires a separate quote. A 10 GiB/month egress assumption is small, but
downloads, artifacts, image builds, and unusual traffic can exceed it. If Cloud
Logging is enabled, retention and ingest must be priced/approved separately.

Pricing references (official Google sources, checked 2026-10-23):

- [E2 general-purpose Compute Engine pricing](https://cloud.google.com/products/compute/pricing/general-purpose)
- [Persistent Disk and snapshot pricing](https://cloud.google.com/compute/disks-image-pricing)
- [External IPv4 and internet egress pricing](https://cloud.google.com/vpc/pricing)
- [Cloud DNS pricing](https://cloud.google.com/dns/pricing)
- [Secret Manager pricing and free usage](https://cloud.google.com/secret-manager/pricing)
- [Google Cloud $300/90-day trial terms](https://cloud.google.com/free/docs/free-cloud-features)

## Google setup and operator commands

These are proposed commands, **not run**. Replace all uppercase placeholders
only in the operator's own approved terminal. The operator must approve each
checkbox before the corresponding external action.

1. Select an existing organization-owned Google Cloud project and confirm a
   trial account is eligible. For the first week, enable only Compute Engine
   and Secret Manager APIs. Set a budget notification; it is a notification,
   not a hard spending cap. Review $393.54/90-day modeled usage against the
   $300 trial before starting it.
2. Create a dedicated VM service account. Grant `roles/secretmanager.secretAccessor`
   only on the two named OAuth and OpenAI secrets. It needs no Owner, Editor,
   project-wide secret access, or service account key. Attach that account to
   the VM with the `cloud-platform` access scope; IAM remains the access control.
3. Create a custom VPC/subnet and ingress rules. Permit TCP 80/443 from the
   public internet. Permit TCP 22 only from IAP's `35.235.240.0/20` range, or
   keep SSH closed and use an approved serial/management path. Do not create
   ingress rules for 8000, 5173, 2375, or 2376. Permit outbound DNS and HTTPS
   required for Google OIDC/JWKS, Secret Manager, OS/image updates, Let's
   Encrypt, and OpenAI. Restrict egress further only after accounting for the
   provider endpoints and update paths.
4. Create the VM and separate state disk in an approved `us-west1` zone, using
   Ubuntu 24.04 LTS amd64, `e2-standard-4`, a 100 GiB standard boot disk, a
   200 GiB `pd-balanced` state disk, and the dedicated runtime service account.
   Set `auto-delete=no` on the state disk. Enable OS Login; grant human
   maintainers `roles/compute.osLogin` and (when using IAP SSH)
   `roles/iap.tunnelResourceAccessor`. Do not distribute SSH keys or VM service
   account keys.
5. Create the production Web OAuth client (separate from localhost testing).
   Configure only the chosen HTTPS origin and exact `/api/cloud-auth/callback`
   redirect. Verify the OAuth consent screen's production/test-user policy.
   Store the client secret and separately approved OpenAI API key in Secret
   Manager; enter neither into Git, chat, an image build argument, or browser
   config. `deploy/fetch-secrets.sh` reads these via the VM service account into
   root-readable, app-UID-only files and prints no payload.
6. Prepare the attached state disk, install Docker Engine/Compose and Caddy,
   set up rootless Docker for a dedicated `sigma-sandbox` OS user, and build the
   two locked research images there. Before launch, verify that the sandbox
   daemon's rootless UID cannot read `/srv/sigma-state` and the running backend
   cannot access a rootful Docker socket. Set exact service limits from the
   approved env file. The example begins with one globally active research job,
   $2 default/user and $15 global inference ceilings.
7. Point DNS to the VM's external address, allow Caddy to acquire HTTPS, and
   verify production OAuth with two explicitly authorized test users, a denied
   identity, administrator revocation, workspace isolation, budget exhaustion,
   and fake-provider failure/unknown-charge paths. No real inference is part of
   this readiness approval.

The intended GCE shape, for operator editing and approval, is:

```sh
gcloud compute instances create sigma-gce-01 \
  --project=PROJECT_ID --zone=us-west1-b \
  --machine-type=e2-standard-4 \
  --service-account=sigma-runtime@PROJECT_ID.iam.gserviceaccount.com \
  --scopes=cloud-platform --tags=sigma-web \
  --image-family=ubuntu-2404-lts-amd64 --image-project=ubuntu-os-cloud \
  --boot-disk-size=100GB --boot-disk-type=pd-standard \
  --create-disk=name=sigma-state,size=200GB,type=pd-balanced,auto-delete=no
```

The following proposed ingress rules are separate billable/security changes.
Apply only after approving the VPC name, source ranges, and target tags:

```sh
gcloud compute firewall-rules create sigma-web-https \
  --project=PROJECT_ID --network=VPC_NAME --direction=INGRESS \
  --action=ALLOW --rules=tcp:80,tcp:443 --source-ranges=0.0.0.0/0 \
  --target-tags=sigma-web
gcloud compute firewall-rules create sigma-iap-ssh \
  --project=PROJECT_ID --network=VPC_NAME --direction=INGRESS \
  --action=ALLOW --rules=tcp:22 --source-ranges=35.235.240.0/20 \
  --target-tags=sigma-web
```

No `gcloud`, Terraform, Docker push, or provisioning command is run by the
validation script. The examples deliberately use no billing activation,
trial-signup, project-creation, or API-enablement command.

## Host setup and launch contract

1. Mount the state disk at `/srv/sigma-state`; create
   `/srv/sigma-state/auth` owned by UID/GID `10001`, mode `0700`. Ensure it is
   mounted before Docker/SIGMA starts. Do not put secrets in this disk.
2. Install Docker Engine with Compose v2 from their official Ubuntu
   repositories. Caddy runs as the pinned Compose edge container. Configure
   Docker's log driver rotation as shown in Compose.
3. Create `sigma-sandbox` as a separate non-sudo user. Install Docker's
   `docker-ce-rootless-extras`, enable lingering, and initialize its rootless
   daemon. Build the existing Python and SageMath recipes while targeting that
   daemon:

   ```sh
   SANDBOX_UID=$(id -u sigma-sandbox)
   sudo -u sigma-sandbox XDG_RUNTIME_DIR="/run/user/$SANDBOX_UID" \
     systemctl --user edit docker.service
   sudo -u sigma-sandbox env DOCKER_HOST="unix:///run/user/$SANDBOX_UID/docker.sock" \
     docker build --platform linux/amd64 -t sigma-research-python:0.1 \
     -f /opt/sigma/current/sandbox-poc/Dockerfile /opt/sigma/current/sandbox-poc
   sudo -u sigma-sandbox env DOCKER_HOST="unix:///run/user/$SANDBOX_UID/docker.sock" \
     docker build --platform linux/amd64 -t sigma-research-sage:10.8 \
     -f /opt/sigma/current/sandbox-poc/Dockerfile.sage /opt/sigma/current/sandbox-poc
   ```

   In the user service override, add these lines so each daemon start exposes
   the socket only to the dedicated sandbox group as well as its owner:

   ```ini
   [Service]
   ExecStartPost=/usr/bin/chgrp sigma-sandbox %t/docker.sock
   ExecStartPost=/usr/bin/chmod 0660 %t/docker.sock
   ```

   Save the override, restart the user daemon, confirm the socket is owned by
   `sigma-sandbox:sigma-sandbox` with mode `0660`, and place its numeric GID and
   socket path in `/etc/sigma/deploy.env`. Do not relax socket permissions to
   world access. Verify the backend can connect and an unrelated host account
   cannot.
4. Install the reviewed checkout at `/opt/sigma/current`. Copy
   `deploy/env.example` to `/etc/sigma/deploy.env`, set the approved non-secret
   values and exact release SHA, then set owner root and mode `0600`. Create
   two Secret Manager entries. Run (with the approved VM service account):

   ```sh
   sudo deploy/fetch-secrets.sh PROJECT_ID GOOGLE_OAUTH_SECRET OPENAI_API_KEY_SECRET
   ```

5. Configure the VM-managed Caddy Compose service and systemd unit to read the
   same env file and use both `deploy/compose.yaml` and
   `deploy/compose.gce.yaml`. The state disk bind override is essential. Start
   only after DNS and OAuth settings are reviewed:

   ```sh
   cd /opt/sigma/current
   docker compose --env-file /etc/sigma/deploy.env \
     -f deploy/compose.yaml -f deploy/compose.gce.yaml up --build --detach
   ```

   The unit should use `Restart=on-failure`, start after `docker.service` and
   `srv-sigma\\x2dstate.mount`, and run the same `compose ... up -d` on boot.
   Do not run the stack until both disks and secrets are present. Public ingress
   reaches only Caddy; backend/frontend addresses remain private to Compose.

## Backup, restart, update, and rollback

- **Restart/recovery:** Compose uses `restart: unless-stopped`; systemd starts
  the stack after Docker and the state-disk mount. SQLite auth, workspaces,
  sessions, artifacts and spend reservations remain on the disk. Existing T22
  recovery treats an interrupted provider attempt as unknown and holds its
  reservation; do not delete or manually edit the ledger after a restart.
- **Application-consistent backup:** Notify users; stop the stack so no SQLite
  transaction or project write is in flight. Create a regional standard
  snapshot of `sigma-state` and a separately encrypted tar copy in a private
  single-region Cloud Storage bucket with uniform bucket-level access and
  public access prevention. Keep at least 14 daily recovery points, track actual
  changed/compressed bytes, and test restore to a new disk before retaining
  production data. Then start the stack and confirm health/auth/workspace and
  research budget endpoints. The 100 GiB snapshot and 50 GiB GCS estimate above
  are budgeting caps/assumptions, not retention guarantees.
- **Proposed manual backup sequence** (all cloud commands require operator
  approval; variables must be verified):

  ```sh
  docker compose --env-file /etc/sigma/deploy.env \
    -f deploy/compose.yaml -f deploy/compose.gce.yaml stop
  gcloud compute disks snapshot sigma-state --project=PROJECT_ID \
    --zone=us-west1-b --snapshot-names="sigma-state-$(date -u +%Y%m%dT%H%M%SZ)"
  tar --one-file-system --numeric-owner -C /srv/sigma-state -czf - . \
    | gpg --encrypt --recipient APPROVED_BACKUP_PUBLIC_KEY \
      --output /tmp/sigma-state-backup.tgz.gpg
  gcloud storage cp /tmp/sigma-state-backup.tgz.gpg gs://APPROVED_PRIVATE_BUCKET/recovery/
  rm -f /tmp/sigma-state-backup.tgz.gpg
  docker compose --env-file /etc/sigma/deploy.env \
    -f deploy/compose.yaml -f deploy/compose.gce.yaml start
  ```

  Use a RAM-backed or otherwise encrypted temporary directory if disk data
  classification requires it; encrypt the exported archive with an approved
  key before upload, and do not put that key on the VM. The state disk snapshot
  provides Google's at-rest encryption but is in the same Google Cloud project.
  Protect backups with separate IAM and test restore by attaching a cloned disk,
  restoring ownership/mode, starting a private test stack, and verifying two
  owners remain isolated before any production recovery. Cloud Storage lifecycle
  expiration and snapshot deletion are destructive and must be separately
  approved.
- **Update:** Review the diff and image digests; retain current tagged images.
  Set `SIGMA_RELEASE` to the candidate commit, build backend/frontend, rebuild
  sandbox images if their source/dependencies changed, run local checks, take a
  consistent backup, and then recreate the stack. Never change the state mount
  or schema/data during image updates.
- **Rollback:** Restore the previous `SIGMA_RELEASE` from
  `/etc/sigma/deploy.env`, recreate only containers without `--volumes`, and
  verify auth, workspaces and budgets. Do not restore an old database over newer
  research unless a human approves the known data-loss window. Code rollback
  does not roll back provider charges or already persisted research.
- **Shutdown:** `docker compose down` preserves persistent state and named Caddy
  certificate volumes. `down --volumes`, state disk deletion, snapshot deletion,
  or trial expiry can destroy data and require an explicit operator decision.

## Approval checklist

Every item below is an operator gate before doing that action. This assignment
does not satisfy any checkbox.

- [ ] Confirm project owner, project ID, organization policy, `us-west1` quota,
  trial eligibility, and the exact trial-credit/billing terms with the account
  owner. Explicitly approve starting the trial; do not activate a paid account
  as an implicit continuation.
- [ ] Approve the modeled ~$133 normalized month / ~$395 for 90 days, the
  expected ~$95 beyond $300, external OpenAI spending as a separate budget,
  domain renewal if applicable, backup retention, logging choice, and maximum
  authorized recurring spend. Create a budget alert and verify it is not a hard
  cap.
- [ ] Approve enabling Compute Engine and Secret Manager APIs, creating the
  dedicated service account, exact IAM bindings, OS Login/IAP grants, VPC,
  firewall rules, public IP, VM, both disks, backup bucket, snapshots, DNS
  zone/records, and all cleanup/retention policies individually.
- [ ] Approve the dedicated `sigma-sandbox` host account, Docker Engine/rootless
  daemon layout, exact UID/GID/socket path, app-user socket access, and a target
  Linux security test proving runner isolation. Reject deployment if it requires
  mounting a rootful daemon socket into FastAPI.
- [ ] Register production Google OAuth web client; confirm consent-screen
  policy, approved production host, exact HTTPS origin and callback, bootstrap
  administrator identity, public invitation contact, invited account list and
  revocation procedure. Do not place actual OAuth secret in source control.
- [ ] Approve creation and initial values of both Secret Manager secrets, the
  VM's access to only those secret resources, rotation/revocation procedure,
  sponsored OpenAI project's independent billing/usage caps, $2 default/user
  allowance, $15 global ceiling, and one-job global concurrency.
- [ ] Approve the initial administrator and each user's access role/allowance,
  external DNS cutover, Caddy certificate issuance, real Google OAuth acceptance
  test, backup restore test, and any public pilot invitation. Real inference
  requires a separate explicit approval after these checks.
- [ ] Approve teardown or continued operation before trial expiration/credit
  exhaustion. Export and independently verify all state/backups before resource
  deletion or a paid-account transition.

## Local-only validation and unknowns

Run `./deploy/validate-local.sh` with Docker Engine and Compose v2. It builds
the locked backend/frontend and Caddy images, starts an isolated local stack
with dummy OAuth/provider secret files, checks the SPA and hosted-auth status,
restarts/recreates the backend and verifies the SQLite file remains on the
volume. It calls only local HTTP; it does not use the OpenAI key, contact Google,
activate billing, or provision anything. Build the existing pinned research
images separately with `docker build --platform linux/amd64 ...`; do not run
untrusted source as part of packaging checks.

Local workstation evidence (Apple Silicon host, linux/amd64 images via
emulation): backend 120 MB, frontend 29 MB, Python runner 190 MB, and SageMath
runner 1.47 GB. Both runner images were built from the checked-in recipes and
executed through SIGMA's sandbox adapter with `--network=none`, memory/CPU/PID
limits, read-only root, and non-root user; deterministic `print(6 * 7)` returned
`42` for both. This confirms image build and basic start viability only. The
first local Python build took about two minutes under emulation; first-time
Sage image build on GCE and memory use remain unmeasured.

UNVERIFIED until measured on the approved GCE VM: exact regional invoice,
first-time Sage image build duration/bytes/RAM, VM memory under application plus
Sage concurrency, rootless Docker socket behavior and adversarial isolation,
end-to-end HTTPS certificate issuance, production OAuth client behavior, actual
Secret Manager IAM, snapshot/GCS restore and retention, service boot after VM
restart, and production latency/capacity. The local tests cannot establish
these cloud/runtime properties.
