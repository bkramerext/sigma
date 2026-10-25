# SIGMA Cloud Deployment

**Status:** Deployment planning and local package validation; provisioning, hosted OAuth, and public launch require separate operator approval and live verification.

**Target hostname:** `sigma-research.duckdns.org`. **Hosting:** Google Compute Engine trial candidate. Budget alerts do not cap charges. OpenAI inference charges are separate. Do not execute provisioning commands without explicit authorization.

This document consolidates deployment architecture, executable operator runbook, hosted authentication, and earlier hosting feasibility analysis. **Current implementation and operator instructions are in Parts 1–3. Parts 4–5 are historical alternatives, not approved deployment plans.**

## Contents

1. [Deployment architecture and operations](#part-1-deployment-architecture-and-operations)
2. [Provisioning runbook](#part-2-provisioning-runbook)
3. [Cloud identity and access](#part-3-cloud-identity-and-access)
4. [Hosting decision history](#part-4-hosting-decision-history)
5. [External-host feasibility notes](#part-5-external-host-feasibility-notes)


---

# Part 1: Deployment architecture and operations


This is a reviewed deployment package, not permission to create resources. The
only hosting target in this plan is one Linux Compute Engine VM in Oregon
(`us-west1`), with a dedicated persistent state disk. No resource creation,
billing activation, live Google OAuth exchange, or OpenAI request was performed
for this readiness work.

For the approved resource setup sequence, operator inputs, and commands, see
the [GCP provisioning runbook](#provisioning-runbook). The selected,
registered hostname is `sigma-research.duckdns.org`; update its DuckDNS A record
to the reserved VM static IPv4 when allocated. VM preparation is independent
of DNS propagation, and public ingress/app launch remain gated on OAuth, secret,
and operator approvals.

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
For the selected host these are `https://sigma-research.duckdns.org` and
`https://sigma-research.duckdns.org/api/cloud-auth/callback`.

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

The registered DuckDNS hostname has no Google Cloud DNS managed-zone or query
charges. These estimates supersede the earlier Cloud DNS line in the T42
readiness estimate. DuckDNS is a separate DNS service; no GCP DNS zone is
planned.

### Before public launch

This is the always-on cost after the VM and static address exist but before
public ingress, Compose launch, backups, or user traffic. It excludes variable
outbound traffic for package/image downloads during host setup; actual transfer
is not measured and should be monitored.

| Google Cloud line item | Assumption and rate | Normalized month | 90 days |
| --- | --- | ---: | ---: |
| Compute Engine `e2-standard-4` | 4 vCPU, 16 GiB, 730/2,160 h at about $0.13402284/h | $97.84 | $289.49 |
| Boot Persistent Disk | 100 GiB standard, about $0.0000548/GiB-h | $4.00 | $11.84 |
| State Persistent Disk | 200 GiB balanced, about $0.00013699/GiB-h | $20.00 | $59.18 |
| VM external IPv4 | One in-use standard-VM address at $0.005/h | $3.65 | $10.80 |
| **Pre-public-launch baseline** | VM, both disks, and attached static IPv4 | **$125.49** | **$371.31** |

At the always-on pre-launch baseline, $300 of trial credit lasts about 73 days;
90 days would use about $71.31 beyond that credit if the VM and disks remain
active. A VM stopped after setup avoids VM CPU/RAM charges, but disks and an
attached static address continue to incur costs.

### After public launch

This adds planned backups and an illustrative small traffic allowance to the
pre-launch baseline. Enable/retain snapshots and Cloud Storage backups only
after their separate approval. No Cloud DNS charge is included because the
selected host uses DuckDNS.

| Additional Google Cloud line item | Assumption and rate | Normalized month | 90 days |
| --- | --- | ---: | ---: |
| Regional standard snapshots | Budget 100 GiB stored at $0.000068493/GiB-h | $5.00 | $14.79 |
| Cloud Storage backup copy | 50 GiB single-region Standard at $0.02/GiB-month | $1.00 | $3.00 |
| Internet egress | 10 GiB/month to North America; first 1 GiB/month free, then $0.12/GiB | $1.08 | $3.24 |
| Secret Manager | Two active versions and low-volume reads within current free limits | $0.00 | $0.00 |
| Cloud Logging | Not enabled; Docker local log rotation, no GCP ingest | $0.00 | $0.00 |
| DuckDNS | Existing registered hostname; no Google Cloud DNS resource | $0.00 | $0.00 |
| **Total after launch** | External OpenAI API usage excluded | **$132.57** | **$392.34** |

If the fully deployed post-launch model ran continuously, it would consume the
$300 trial credit around day 69 and use about $92.34 beyond the credit over 90
days. These are planning estimates, not quotes; actual egress, backup size,
tax, regional pricing, and first-build transfer vary. If Cloud Logging is
enabled, retention and ingest must be priced and approved separately. Google
Cloud's free trial closes the account and stops associated resources when the
credit is exhausted or 90 days elapse without a paid-account upgrade. Do not
assume free-tier eligibility offsets these costs or upgrade automatically.

Pricing references (official Google sources, checked 2026-10-23):

- [E2 general-purpose Compute Engine pricing](https://cloud.google.com/products/compute/pricing/general-purpose)
- [Persistent Disk and snapshot pricing](https://cloud.google.com/compute/disks-image-pricing)
- [External IPv4 and internet egress pricing](https://cloud.google.com/vpc/pricing)
- [Secret Manager pricing and free usage](https://cloud.google.com/secret-manager/pricing)
- [Google Cloud $300/90-day trial terms](https://cloud.google.com/free/docs/free-cloud-features)
- [DuckDNS service and update API](https://www.duckdns.org/spec.jsp)

## Google setup and operator commands

These are proposed commands, **not run**. Replace all uppercase placeholders
only in the operator's own approved terminal. The operator must approve each
checkbox before the corresponding external action.

1. Select an existing organization-owned Google Cloud project and confirm a
   trial account is eligible. Enable only APIs listed in the
   [provisioning runbook](#provisioning-runbook). Set a budget alert; it
   is a notification, not a hard spending cap. Review the $371.31/90-day
   pre-launch baseline and $392.34/90-day post-launch estimate against the
   $300 trial before starting it.
2. Create a dedicated VM service account. Grant `roles/secretmanager.secretAccessor`
   only on the two named OAuth and OpenAI secrets. It needs no Owner, Editor,
   project-wide secret access, or service account key. Attach that account to
   the VM with the `cloud-platform` access scope; IAM remains the access control.
3. Create a custom VPC/subnet and ingress rules. Permit TCP 22 only from IAP's
   `35.235.240.0/20` range, or keep SSH closed and use an approved
   serial/management path. Open public TCP 80/443 only after the hostname's
   DuckDNS A record resolves to the reserved static IP and OAuth/secrets and
   launch approvals are ready. Do not create
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
7. Confirm `sigma-research.duckdns.org` points to the VM's static external
   IPv4. After OAuth/secrets and launch approvals, open web ingress and allow
   Caddy to acquire HTTPS. Verify production OAuth with two authorized test
   users, a denied
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
   sudo env SIGMA_DEPLOY_ENV_FILE=/etc/sigma/deploy.env \
     SIGMA_STATE_DISK_MOUNT=/srv/sigma-state \
     /opt/sigma/current/deploy/start-gce.sh
   ```

   The unit should use `Restart=on-failure`, start after `docker.service` and
   `srv-sigma\\x2dstate.mount`, and run the guarded `start-gce.sh` on boot with
   `SIGMA_DEPLOY_ENV_FILE=/etc/sigma/deploy.env` and
   `SIGMA_STATE_DISK_MOUNT=/srv/sigma-state`. Do not invoke Compose `up` or
   `start` directly for production startup.
   Do not run the stack until both disks and secrets are present. Public ingress
   reaches only Caddy; backend/frontend addresses remain private to Compose.

## Backup, restart, update, and rollback

- **Restart/recovery:** Compose uses `restart: unless-stopped`; systemd invokes
  guarded `start-gce.sh` after Docker and the state-disk mount. SQLite auth,
  workspaces, sessions, artifacts and spend reservations remain on the disk.
  Existing T22 recovery treats an interrupted provider attempt as unknown and
  holds its reservation; do not delete or manually edit the ledger after a restart.
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
  sudo env SIGMA_DEPLOY_ENV_FILE=/etc/sigma/deploy.env \
    SIGMA_STATE_DISK_MOUNT=/srv/sigma-state \
    /opt/sigma/current/deploy/start-gce.sh
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
- [ ] Approve the modeled ~$125.49 normalized month / $371.31 for 90 days
  before public launch and ~$132.57 / $392.34 after launch, with the latter
  using estimated backups and traffic; estimate ~$92 beyond $300 over 90 days.
  Approve external OpenAI spending as a separate budget, backup retention,
  logging choice, and maximum recurring spend. Create a budget alert and verify
  it is not a hard cap.
- [ ] Approve enabling Compute Engine and Secret Manager APIs, creating the
  dedicated service account, exact IAM bindings, OS Login/IAP grants, VPC,
  firewall rules, public IP, VM, both disks, backup bucket, snapshots, the
  DuckDNS record update, and all cleanup/retention policies individually.
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
  DuckDNS record update to the reserved IP, Caddy certificate issuance, real Google OAuth acceptance
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


---

# Part 2: Provisioning runbook


This runbook turns the approved Compute Engine plan in
[#deployment-architecture-and-operations](#deployment-architecture-and-operations) into staged operator commands. It does
not authorize resource creation. The commands below are for one `us-west1` VM
and require review and explicit approval by the project and billing owners.
Do not paste secrets into shell commands, GitHub, chat, or source control.

## Provision the VM before public launch

The selected and registered hostname is
`sigma-research.duckdns.org`. VM provisioning, persistent disks, VPC,
IAP-only administration, and the reserved regional static IPv4 do not depend
on DNS propagation or production OAuth. Reserve and attach the static IP,
record it, then update the DuckDNS A record to that address. DNS may resolve
before public service is ready; keep web firewall ingress closed until the
launch gates below are met.

Do not start the SIGMA Compose stack yet. `deploy/compose.yaml` requires
`SIGMA_DOMAIN`, the production Google OAuth client ID, secret files, and the
rootless sandbox socket. It is configured for HTTPS at the selected hostname.
Provision and harden the VM, mount the state disk, install Docker, stage the
reviewed release, build the pinned images, and validate privately through
IAP/SSH and local health requests. Do not open TCP 80/443 or start Compose until
DNS resolves to the reserved IP, production OAuth and secrets are ready, and
the required operator approvals are recorded.

## Prerequisites and operator decisions

Before proceeding, the operator must identify and approve:

- Existing organization-owned `PROJECT_ID`, project owner, billing account,
  organization policy, and whether the project is linked to that billing
  account. Project creation is out of scope.
- Account eligibility and explicit authorization to activate the Google Cloud
  free trial, if applicable. Trial activation is a human-only Google Console
  action and is not included as a command. Do not upgrade to paid billing as
  an implicit continuation.
- Region `us-west1` and a zone with quota/capacity, proposed `us-west1-b`;
  `e2-standard-4`, 100 GiB `pd-standard` boot disk, 200 GiB `pd-balanced`
  state disk, custom VPC CIDR, maintenance window, and expected spend.
- Named operator email(s), billing-alert recipient, and an IAM administrator.
  Require IAP SSH; do not allow public SSH.
- Runtime service account name `sigma-runtime`, two Secret Manager resource
  names, and named owners authorized to create/update their versions. Secret
  payloads must come from their owners through the approved secure entry flow.
- Confirm access to the registered DuckDNS hostname and its approved secure
  update path. Never place a DuckDNS account token in this runbook, source
  control, or the application env file. No domain purchase is needed for the
  selected hostname.

Placeholders below are deliberately conspicuous. Set them only in the
operator's reviewed terminal; never export secret values.

```sh
export PROJECT_ID='APPROVED_EXISTING_PROJECT_ID'
export BILLING_ACCOUNT_ID='APPROVED_BILLING_ACCOUNT_ID'
export OPERATOR_EMAIL='NAMED_OPERATOR_EMAIL'
export REGION='us-west1'
export ZONE='us-west1-b'
export VM_NAME='sigma-gce-01'
export VPC_NAME='sigma-vpc'
export SUBNET_NAME='sigma-us-west1'
export SUBNET_CIDR='10.42.0.0/24' # approve against network plan first
export RUNTIME_SA='sigma-runtime'
export OAUTH_SECRET='sigma-google-oauth-client-secret'
export OPENAI_SECRET='sigma-sponsored-openai-api-key'
export SIGMA_DOMAIN='sigma-research.duckdns.org'
export TRIAL_START_DATE='YYYY-MM-DD' # confirmed trial credit start date
export TRIAL_END_DATE='YYYY-MM-DD'   # confirmed 90-day trial end date
```

## Phase 1 — preparation and cost safeguards

### Read-only preflight

These commands inspect local identity and the selected project; they create no
cloud resources.

```sh
gcloud auth list --filter='status:ACTIVE' --format='table(account,status)'
gcloud config get-value project
gcloud projects describe "$PROJECT_ID" --format='yaml(projectId,lifecycleState,parent)'
gcloud billing projects describe "$PROJECT_ID"
gcloud compute zones describe "$ZONE" --project="$PROJECT_ID"
gcloud compute machine-types describe e2-standard-4 --zone="$ZONE" --project="$PROJECT_ID"
gcloud compute images describe-from-family ubuntu-2404-lts-amd64 \
  --project=ubuntu-os-cloud
gcloud compute project-info describe --project="$PROJECT_ID"
```

Stop if the active account, project, billing link, quota, approved CIDR, or
Ubuntu image differs from the approved plan. Record actual quota and selected
image version. Do not silently switch zone, machine, disk type, or image.

### Trial and budget alert gate

Trial activation is an explicit operator step in Google Cloud Console. The
current trial offers $300 credit over 90 days; it is not a spend cap. If credit
is exhausted or 90 days elapse without upgrading, the trial billing account
closes and associated projects/resources stop. Trial time cannot be paused or
extended. Never enable paid billing to keep the VM running without separate
approval. See [official trial terms](https://cloud.google.com/free/docs/free-cloud-features).

After billing is intentionally linked/activated and before creating billable
resources, create a project-filtered $300 budget alert. It excludes credits to
measure underlying project usage against the trial credit amount. Alerts can
be delayed and do not stop or cap resources. Confirm billing administrators
receive notifications and verify the budget in Cloud Billing before continuing.
The budget API must be enabled first; enabling an API is an externally visible
project change and needs project-owner approval:

```sh
gcloud services enable billingbudgets.googleapis.com --project="$PROJECT_ID"
```

```sh
gcloud billing budgets create \
  --billing-account="$BILLING_ACCOUNT_ID" \
  --display-name="SIGMA $PROJECT_ID trial usage guard" \
  --budget-amount=300USD \
  --start-date="$TRIAL_START_DATE" --end-date="$TRIAL_END_DATE" \
  --filter-projects="projects/$PROJECT_ID" \
  --credit-types-treatment=exclude-all-credits \
  --threshold-rule=percent=0.50 \
  --threshold-rule=percent=0.75 \
  --threshold-rule=percent=0.90 \
  --threshold-rule=percent=1.00 \
  --threshold-rule=percent=0.90,basis=forecasted-spend
```

Safeguards:

1. Approve a project-only budget and recipients; inspect actual and forecast
   spend daily during provisioning.
2. Label resources. Do not create unrelated services, GPUs, load balancers,
   Cloud NAT, managed databases, logging ingestion, DNS zones, or backup
   buckets under this assignment.
3. Stop the VM when it is not needed. Stopping removes VM CPU/RAM charges, but
   disks and an assigned IP can continue to charge. Deleting a VM does not
   delete the independently created state disk; review every resource before
   cleanup.
4. Budgets notify; they do not enforce a ceiling. There is no safe CLI hard
   cap for this deployment. Shutdown or teardown is a human action requiring a
   data-preservation review.
5. Keep state-disk auto-delete disabled and verify a backup before destructive
   cleanup or schema/data changes.

### APIs to enable after authorization

Enable only APIs needed here. `iap.googleapis.com` is needed for IAP SSH.
Cloud DNS is not part of the selected DuckDNS setup; Cloud Logging stays off
unless separately approved. API
activation changes the project, though these APIs have no direct per-request
price.

```sh
gcloud services enable \
  compute.googleapis.com \
  iam.googleapis.com \
  cloudresourcemanager.googleapis.com \
  secretmanager.googleapis.com \
  iap.googleapis.com \
  billingbudgets.googleapis.com \
  --project="$PROJECT_ID"
```

The budget command uses the Cloud Billing Budgets API, even though the budget
is attached to the billing account. Do not enable DNS, Artifact Registry,
Cloud Logging, or other APIs “just in case.”

## Phase 2 — resource creation

Every command here changes cloud state or may incur charges. Require the named
project owner to approve each resource group before running it. Use explicit
`--project` flags.

### Dedicated VM identity and secret access

Create a VM service account without keys. Grant access only to the two
approved secrets, not project-wide secret access. Create secret *resources*
with no payload; a separate owner enters values through the approved Secret
Manager interface. Never place secret contents in command arguments, shell
variables, metadata, env files, or GitHub.

```sh
gcloud iam service-accounts create "$RUNTIME_SA" \
  --project="$PROJECT_ID" --display-name='SIGMA hosted runtime'
export RUNTIME_SA_EMAIL="$RUNTIME_SA@$PROJECT_ID.iam.gserviceaccount.com"

gcloud secrets create "$OAUTH_SECRET" --project="$PROJECT_ID" \
  --replication-policy=automatic --labels=app=sigma,environment=production
gcloud secrets create "$OPENAI_SECRET" --project="$PROJECT_ID" \
  --replication-policy=automatic --labels=app=sigma,environment=production

gcloud secrets add-iam-policy-binding "$OAUTH_SECRET" --project="$PROJECT_ID" \
  --member="serviceAccount:$RUNTIME_SA_EMAIL" \
  --role=roles/secretmanager.secretAccessor
gcloud secrets add-iam-policy-binding "$OPENAI_SECRET" --project="$PROJECT_ID" \
  --member="serviceAccount:$RUNTIME_SA_EMAIL" \
  --role=roles/secretmanager.secretAccessor
```

An authorized secret owner later adds versions through the secure approved
mechanism. Do not use shell history or inline `--data-file=<(...)` patterns.
On the VM, use the existing `deploy/fetch-secrets.sh PROJECT_ID OAUTH_SECRET
OPENAI_SECRET` as root. It reads via the attached VM identity and writes
app-readable files under `/run`.

### VPC and IAP administration firewall

Use a custom VPC/subnet so default-network rules do not broaden access. Confirm
`SUBNET_CIDR` is approved and does not overlap before creation.

```sh
gcloud compute networks create "$VPC_NAME" --project="$PROJECT_ID" \
  --subnet-mode=custom --bgp-routing-mode=regional
gcloud compute networks subnets create "$SUBNET_NAME" --project="$PROJECT_ID" \
  --network="$VPC_NAME" --region="$REGION" --range="$SUBNET_CIDR" \
  --enable-private-ip-google-access

gcloud compute firewall-rules create sigma-allow-iap-ssh \
  --project="$PROJECT_ID" --network="$VPC_NAME" --direction=INGRESS \
  --priority=1000 --action=ALLOW --rules=tcp:22 \
  --source-ranges=35.235.240.0/20 --target-tags=sigma-iap-ssh
```

There is no public TCP/22 rule. Do not create ingress for 8000, 5173, 2375,
or 2376. Public TCP 80/443 is deferred to Phase 3 until the selected hostname
resolves to the reserved IP, production OAuth and secrets are ready, and
operator approvals are recorded.

### IAM grants for named humans

The owner must review the existing policy and grant only named operators.
`roles/compute.osAdminLogin` permits sudo-level VM login and is needed for
initial host setup; remove it after setup if routine maintenance can use the
non-admin role. IAP tunnel access is separate. The VM creator needs
`roles/iam.serviceAccountUser` only on the runtime service account.

```sh
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="user:$OPERATOR_EMAIL" --role=roles/compute.osAdminLogin
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="user:$OPERATOR_EMAIL" --role=roles/iap.tunnelResourceAccessor
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA_EMAIL" \
  --project="$PROJECT_ID" --member="user:$OPERATOR_EMAIL" \
  --role=roles/iam.serviceAccountUser
```

These are examples of required access, not a request for Owner or Editor. If
the operator lacks Compute/network/disk permissions, an IAM administrator must
grant approved least privilege or run reviewed commands. Do not broaden access
to make a failed command pass.

### State disk, reserved address, and VM

Create the independent state disk first so VM deletion cannot remove it.
Reserve a regional static external IPv4 now and attach it to the VM; DNS
propagation is not a prerequisite. Record the address. The assigned address
costs the in-use rate even before DNS points to it. Do not leave it unassigned;
unused static IPs cost more. Keep public web ingress closed until Phase 3.

```sh
gcloud compute disks create sigma-state --project="$PROJECT_ID" \
  --zone="$ZONE" --size=200GB --type=pd-balanced \
  --labels=app=sigma,environment=production
gcloud compute addresses create sigma-web-ip --project="$PROJECT_ID" \
  --region="$REGION" --network-tier=PREMIUM \
  --description='SIGMA production endpoint for sigma-research.duckdns.org'
export STATIC_IP="$(gcloud compute addresses describe sigma-web-ip \
  --project="$PROJECT_ID" --region="$REGION" --format='value(address)')"
printf 'Reserved static IP: %s\n' "$STATIC_IP"
```

Once `STATIC_IP` has been returned, the hostname owner must update the DuckDNS
A record for `sigma-research.duckdns.org` to exactly that IPv4 address using
DuckDNS's approved account/update path. Never put the DuckDNS token in command
history, project metadata, `/etc/sigma/deploy.env`, or this repository. Verify
the A record using a public DNS resolver. Do not create a Cloud DNS zone or
add an AAAA record unless IPv6 is separately configured and approved. This
DNS update does not open the VM or authorize application launch.

After recording the returned IP and reviewing the create plan, create the VM
with the attached non-auto-delete state disk. This enables OS Login, blocks
project SSH keys, attaches the runtime identity, and grants only the IAP
firewall tag.

```sh
gcloud compute instances create "$VM_NAME" --project="$PROJECT_ID" \
  --zone="$ZONE" --machine-type=e2-standard-4 \
  --network="$VPC_NAME" --subnet="$SUBNET_NAME" \
  --address=sigma-web-ip --network-tier=PREMIUM \
  --service-account="$RUNTIME_SA_EMAIL" --scopes=cloud-platform \
  --tags=sigma-iap-ssh \
  --image-family=ubuntu-2404-lts-amd64 --image-project=ubuntu-os-cloud \
  --boot-disk-size=100GB --boot-disk-type=pd-standard \
  --boot-disk-device-name=sigma-boot \
  --disk=name=sigma-state,device-name=sigma-state,mode=rw,boot=no,auto-delete=no \
  --metadata=enable-oslogin=TRUE,block-project-ssh-keys=TRUE \
  --shielded-secure-boot --shielded-vtpm --shielded-integrity-monitoring \
  --deletion-protection \
  --labels=app=sigma,environment=production,owner=approved-owner
```

If current stable `gcloud` rejects a flag, stop and check its official
reference; do not substitute a broader configuration. Confirm VM state, disk
attachments, IP, tags, labels, metadata, and service account before host login:

```sh
gcloud compute instances describe "$VM_NAME" --project="$PROJECT_ID" \
  --zone="$ZONE" --format='yaml(status,machineType,disks,networkInterfaces,serviceAccounts,tags,metadata,labels)'
gcloud compute disks describe sigma-state --project="$PROJECT_ID" --zone="$ZONE" \
  --format='yaml(status,sizeGb,type,users)'
gcloud compute addresses describe sigma-web-ip --project="$PROJECT_ID" \
  --region="$REGION" --format='yaml(address,status,users)'
gcloud compute ssh "$VM_NAME" --project="$PROJECT_ID" --zone="$ZONE" \
  --tunnel-through-iap
```

### Create a backup target only after separate approval

Backups are part of the deployment design but are intentionally not necessary
for initial VM provisioning. Before launch, separately approve a private
single-region Cloud Storage bucket with uniform bucket-level access, public
access prevention, backup encryption, lifecycle/retention policy, and backup
IAM. Estimate 50 GiB Standard storage at approximately $1/month before
operations/transfer. Do not create it under this runbook without approval.

## Phase 3 — deployment after the VM exists

### Private host setup before public launch

1. Through IAP, verify Ubuntu release, disk identity/size, OS Login, shielded
   state, package-update policy, time sync, and absence of public SSH. Format
   and mount the state disk at `/srv/sigma-state` only after verifying it is
   the new `sigma-state` disk.
2. Install Docker Engine/Compose using the reviewed Ubuntu procedure in
   `docs/#deployment-architecture-and-operations`. Create the separate `sigma-sandbox` account and
   rootless Docker service. Verify runner isolation from `/srv/sigma-state`
   and host root. Never mount a rootful Docker socket into FastAPI.
3. Stage the reviewed release at `/opt/sigma/current`, create root-only
   `/etc/sigma/deploy.env` from `deploy/env.example`, and build the pinned
   backend/frontend and Python/SageMath images locally. Do not start Compose
   until domain/OAuth/secrets/rootless socket values exist. Record build time,
   peak RAM, disk headroom, and image sizes; stop if approved limits are
   exceeded.
4. Validate privately via localhost checks or an IAP tunnel. Keep 80/443
   closed and do not publish application ports.

`deploy/compose.yaml` requires `SIGMA_DOMAIN`, a production OAuth client ID,
secret files, and the rootless socket, so full Compose startup is deliberately
after all launch gates. VM creation, disk mount, Docker installation, and
image builds can complete before DNS propagation/OAuth/secret approval.

### Selected hostname, production OAuth, secrets, public ingress, launch

Each action below needs explicit operator approval:

1. Confirm the DuckDNS A record `sigma-research.duckdns.org` equals the
   reserved `STATIC_IP`; resolve it from an external resolver. No Cloud DNS
   API, zone, delegation, or purchase is needed. If DNS does not match, stop.
2. Create a production Google OAuth Web client, separate from localhost
   testing, with origin `https://sigma-research.duckdns.org` and exact callback
   `https://sigma-research.duckdns.org/api/cloud-auth/callback`. Verify
   consent-screen policy and approved admin/test-user list. Secret owner stores
   OAuth secret and separately authorized OpenAI key in the approved Secret
   Manager resources through the secure interface.
3. Set `SIGMA_DOMAIN=sigma-research.duckdns.org`, TLS contact, admin/contact,
   OAuth client ID,
   release SHA, state mount, and actual rootless socket/GID in
   `/etc/sigma/deploy.env`. Keep only file paths for secret settings. Set root
   ownership and mode `0600`.
4. Run `sudo /opt/sigma/current/deploy/fetch-secrets.sh "$PROJECT_ID"
   "$OAUTH_SECRET" "$OPENAI_SECRET"`. Check owner/mode/size without
   displaying payloads. Confirm sponsored inference budgets/access and every
   required operator approval are recorded.
5. Once DNS resolves to the reserved IP and OAuth, secrets, and approvals are
   ready, create web ingress, add the web tag, and start Compose. Caddy obtains
   HTTPS only after DNS and firewall checks.

```sh
gcloud compute firewall-rules create sigma-allow-web \
  --project="$PROJECT_ID" --network="$VPC_NAME" --direction=INGRESS \
  --priority=1000 --action=ALLOW --rules=tcp:80,tcp:443 \
  --source-ranges=0.0.0.0/0 --target-tags=sigma-web
gcloud compute instances add-tags "$VM_NAME" --project="$PROJECT_ID" \
  --zone="$ZONE" --tags=sigma-web
```

After verifying env and secret files on the VM, validate the merged Compose
configuration (read-only; no containers start):

```sh
cd /opt/sigma/current
docker compose --env-file /etc/sigma/deploy.env \
  -f deploy/compose.yaml -f deploy/compose.gce.yaml config --quiet
```

Then use only the guarded production startup path:

```sh
sudo env SIGMA_DEPLOY_ENV_FILE=/etc/sigma/deploy.env \
  SIGMA_STATE_DISK_MOUNT=/srv/sigma-state \
  /opt/sigma/current/deploy/start-gce.sh
```

Keep container ports private. Never enable public TCP/8000, 5173, 2375, or
2376. Use the backup/update/rollback instructions in `docs/#deployment-architecture-and-operations`
before any release update.

## Cost estimate and trial limitations

Planning estimate reconciled with `docs/#deployment-architecture-and-operations`, USD list prices
checked 2026-10-23, 730 hours/month and 2,160 hours/90 days, before tax,
discounts, price changes, and OpenAI use. The selected registered hostname is
`sigma-research.duckdns.org`; it uses DuckDNS, so no Cloud DNS zone/query
charges are included.

### Before public launch

Always-on VM, disks, and attached static IP, before public traffic, backups,
or public Compose launch. One-time image/package download egress during setup
is not measured or included; monitor actual transfer.

| Item | Assumption | Monthly | 90 days |
| --- | --- | ---: | ---: |
| `e2-standard-4` | Always on, ~`$0.13402284`/h | $97.84 | $289.49 |
| 100 GiB standard boot disk | `$0.0000548`/GiB-h | $4.00 | $11.84 |
| 200 GiB balanced state disk | `$0.00013699`/GiB-h | $20.00 | $59.18 |
| In-use static external IPv4 | `$0.005`/h | $3.65 | $10.80 |
| **Pre-launch baseline** |  | **$125.49** | **$371.31** |

The $300 credit covers about 73 days at this baseline; 90 continuously active
days exceed the credit by about $71.31.

### After public launch

This is the baseline plus separately approved planned backup storage and an
illustrative small traffic allowance. Snapshots/backups are not prerequisites
for creating the VM; enable them only after approval.

| Additional item | Assumption | Monthly | 90 days |
| --- | --- | ---: | ---: |
| Regional standard snapshots | 100 GiB allowance at `$0.000068493`/GiB-h | $5.00 | $14.79 |
| Cloud Storage backup copy | 50 GiB Standard at `$0.02`/GiB-month | $1.00 | $3.00 |
| Internet egress | 10 GiB/mo; first GiB free, then `$0.12`/GiB | $1.08 | $3.24 |
| DuckDNS | Registered hostname; no GCP managed zone | $0.00 | $0.00 |
| Secret Manager / Cloud Logging | Low-volume secret use / logging disabled | $0.00 | $0.00 |
| **After-launch modeled total** | OpenAI API usage excluded | **$132.57** | **$392.34** |

The after-launch model consumes $300 around day 69 and exceeds it by about
$92.34 over 90 days. Egress, backups, tax, and regional prices vary. An
unassigned static IPv4 costs more than an attached in-use address; stopping the
VM removes CPU/RAM charges but not disk charges. See the [Pricing
Calculator](https://cloud.google.com/products/calculator), current [Compute](https://cloud.google.com/products/compute/pricing/general-purpose),
[disk/snapshot](https://cloud.google.com/compute/disks-image-pricing),
[network/IP](https://cloud.google.com/vpc/pricing), [Secret Manager](https://cloud.google.com/secret-manager/pricing),
and [DuckDNS update API](https://www.duckdns.org/spec.jsp) before approval.
This estimate is not a quote.

Trial use requires explicit account-owner approval. Trial credit does not
cover OpenAI API usage. Do not upgrade to paid billing to avoid shutdown
without explicit budget authorization. Budget alerts do not cap spend. Trial
closure stops associated resources, so the state disk is not an independent
backup; decide on recovery, shutdown, or paid continuation before trial end.

## Post-provision validation checklist

- [ ] VM is in approved project/zone with the approved machine, Ubuntu amd64,
  shielded settings, deletion protection, and resource labels.
- [ ] Static IPv4 is attached and recorded; DuckDNS A record for
  `sigma-research.duckdns.org` resolves to it.
- [ ] State disk is the approved 200 GiB balanced volume, attached with
  auto-delete disabled, mounted at `/srv/sigma-state`, and survives VM restart.
- [ ] IAP SSH works only for named maintainers; no public `:22`; OS Login is
  enabled; runtime service account has no key and only two secret-level grants.
- [ ] Until DNS, production OAuth, secrets, and all required approvals are
  ready, only IAP TCP/22 is allowed; public 80/443 remain closed. No app or
  Docker ports are public.
- [ ] Budget and recipients are verified in Billing; operator understands it
  is an alert rather than a hard limit.
- [ ] Docker/Compose, mount-before-start ordering, and rootless sandbox daemon
  are installed. Backend can access only the rootless socket; runner and other
  OS users cannot access app state or rootful Docker.
- [ ] Locked backend/frontend/Python/Sage images build locally. Bounded offline
  runner returns expected output under configured limits. Record build time,
  peak RAM, disk headroom, and image sizes.
- [ ] Before public launch: OAuth origin/callback match the selected hostname;
  secret files have correct ownership/mode without displaying values; Caddy has HTTPS;
  `/api/cloud-auth/status` reports `target=hosted`; workspace isolation,
  admin revocation, exhausted spend limits, provider failure, and uncertain
  charge behavior are checked using deterministic fake/local provider flows.
- [ ] Before inviting users: take and restore-test an application-consistent
  backup; prove owner isolation; review spend/alerts; record recovery owner
  and trial-expiry/teardown decision.

## Validation evidence and references

This runbook adds no provisioning automation. Review commands as text only;
do not run `gcloud`, contact Google, access credentials, push images, or call
providers while authoring/reviewing it.

- [gcloud budgets create](https://cloud.google.com/sdk/gcloud/reference/billing/budgets/create)
- [gcloud VM create](https://cloud.google.com/sdk/gcloud/reference/compute/instances/create)
- [gcloud disks create](https://cloud.google.com/sdk/gcloud/reference/compute/disks/create)
- [gcloud addresses create](https://cloud.google.com/sdk/gcloud/reference/compute/addresses/create)
- [VPC firewall rules](https://cloud.google.com/vpc/docs/using-firewalls)
- [Service account IAM](https://cloud.google.com/iam/docs/service-accounts)
- [IAP TCP forwarding](https://cloud.google.com/iap/docs/using-tcp-forwarding)
- [Free trial terms](https://cloud.google.com/free/docs/free-cloud-features)


---

# Part 3: Cloud identity and access


Cloud identity is opt-in. Local SIGMA keeps its existing ChatGPT sign-in and
continues to use its current single-user API behavior when
`SIGMA_CLOUD_AUTH_ENABLED` is unset or false. Hosted Google identity is not an
AI-provider credential and does not authorize inference. The current cloud mode
blocks `/api/ai/*`; a future hosted provider design must provide explicit user
authorization and billing controls.

Set these deployment environment values to enable cloud authentication:

| Variable | Purpose |
|---|---|
| `SIGMA_CLOUD_AUTH_ENABLED=true` | Explicitly enables hosted authorization. |
| `SIGMA_CLOUD_PUBLIC_ORIGIN=https://sigma.example.org` | Exact public HTTPS origin, with no path or trailing slash. Used for callback and CSRF origin validation. |
| `GOOGLE_OIDC_CLIENT_ID` | Google OAuth web client ID. |
| `GOOGLE_OIDC_CLIENT_SECRET` | Google OAuth web client secret; keep server-side only. |
| `SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL` | Verified email permitted to establish the first administrator. Its first Google subject is permanently bound in the auth database. |
| `SIGMA_CLOUD_ADMIN_CONTACT_EMAIL` | Public contact address used to prefill an invitation request. SIGMA opens a mail draft and never sends it. |
| `SIGMA_CLOUD_AUTH_HOME=/var/lib/sigma-auth` | Absolute, service-owned private directory; mode 0700. The SQLite database is mode 0600. |
| `SIGMA_CLOUD_DEMO_AUDIT=/opt/sigma/cloud-demo/handshake-demo-audit.json` | Absolute path to the curated, server-owned, read-only Project Audit v2 snapshot served to guests. It is separate from private project storage and required for the public Demo. |

Create a Google OAuth client for a web application. Register the exact redirect
URI `${SIGMA_CLOUD_PUBLIC_ORIGIN}/api/cloud-auth/callback`. SIGMA uses Google's
fixed OIDC discovery document, authorization-code flow, PKCE S256, state and
nonce. It validates the ID-token signature using Google's published JWKS and
requires the Google issuer, exact client audience, unexpired token, matching
nonce, stable subject, and `email_verified: true`. It rejects multi-audience
tokens and mismatched authorized-party claims.

After setup, the configured bootstrap address can sign in once to bind its stable
Google subject as administrator. Administrators can add exact email entries or
exact email domains in Access Management. Entries authorize accounts; no email
is delivered. Domain rules compare the complete verified-email domain after
case normalization, so suffix/lookalike domains do not match. An explicit
revoked email rule takes precedence over a domain allow rule. Revocation is
checked on every request and removes matching active sessions. Re-adding a
revoked email reactivates that exact entry. The bootstrap admin remains
configuration-bound and cannot be revoked in the UI.

Sessions are random opaque values stored only as SHA-256 digests in SQLite.
Cookies are `Secure`, `HttpOnly`, `SameSite=Lax`, host-only `__Host-` cookies,
and expire after eight hours. State/nonce/verifier records are one-use and
expire after five minutes. Unsafe requests require the configured exact Origin.
The auth database contains no provider tokens or project data.

## Real Google sign-in for local SIGMA

Local Google authentication starts only when the bootstrap administrator email
is configured. Without that setting, `./sigma start` keeps the existing local
single-user behavior. Add the operator's actual Gmail address to `~/.bashrc`:

```dotenv
export SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL="you@gmail.com"
```

Create a Google Cloud project and configure the OAuth consent screen for the
intended test users. Create an OAuth client ID of type **Web application**, add
`http://127.0.0.1:5173` under Authorized JavaScript origins, and register this
exact Authorized redirect URI:
`http://127.0.0.1:5173/api/cloud-auth/callback`. Put the resulting client ID and
secret in the checkout's ignored `.env` (never commit or expose the secret):

```dotenv
GOOGLE_OIDC_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OIDC_CLIENT_SECRET=your-client-secret
```

Reload the shell configuration, then run the requested command:

```sh
source ~/.bashrc
./sigma start --nav
```

The presence of the configured bootstrap email opts this local launch into real
Google sign-in; the launcher supplies the loopback-only auth settings and stores
the private access database below `~/.sigma/local-cloud-auth`. The first
verified login binds both the configured email and Google's immutable subject
as this local installation's administrator. Every later login must match both
values. Other identities need an explicit authorization entry. The bootstrap
administrator cannot be revoked through Access Management.

The launcher intentionally does not execute or source shell startup files.
The bootstrap email must be exported into the same shell environment that runs
`./sigma start --nav`. For example, if it is stored in `~/.bashrc`, run
`source ~/.bashrc` in that shell first (or configure the startup file used by
your shell). You can verify presence without printing the address with
`test -n "$SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL"`. When OAuth client credentials
are present but the bootstrap email is absent from the launch environment,
SIGMA keeps local single-user mode and reports which setting is missing; it does
not silently enable Google authentication or infer an administrator identity.

Local OAuth is strictly loopback HTTP: its session cookies are `HttpOnly` and
`SameSite=Lax` but cannot be `Secure` on localhost. The callback origin is
hard-coded by the launcher; the auth service accepts only the exact loopback
origin and still verifies state, nonce, PKCE, ID-token signature, issuer,
audience, subject, verified email, and server-side role. It never applies to
hosted HTTPS deployments. Local login uses the normal local project store and
local access database; it does not administer or share state with hosted SIGMA.
For actual hosted administration, sign in to the hosted service itself. There
is no simulated administrator mode.

Google and ChatGPT controls reuse the existing Home and project-header pills.
Google identity and sign-out are shown only in the Google pill dialog; account
emails are not shown in the header. When a valid Google identity is not
authorized, the app displays “Access not yet granted” in the SIGMA Home design.
Only that denied flow can read its verified email: the server keeps it in a
short-lived private-database record behind an opaque `Secure`, `HttpOnly` cookie
for up to ten minutes. It is not returned by status, does not create a session
or workspace, and is deleted when Use Another Account starts a fresh
`prompt=select_account` login. The screen offers a prefilled `mailto:` invitation
request to the configured contact.
The contact address is intentionally public; access rules and other accounts
remain private. `/demo` serves the same read-only curated project to anonymous
visitors, denied identities and signed-in users. Its dedicated API accepts no
project ID or filesystem path: it loads only `SIGMA_CLOUD_DEMO_AUDIT`, a
service-owned saved audit snapshot kept outside private project storage. The
snapshot contains the project, saved strategies, sessions, outcomes, research
evidence and analysis. JSON audit and Text/HTML/LaTeX reports are generated from
that snapshot without models, agents, computation, per-visitor copies or writes.
Keep the configured file in a service-owned directory that is not writable by
group or others, and review its contents before deployment. The server resolves
the file and rejects it if it falls under either the configured workspace root
or `$SIGMA_CLOUD_AUTH_HOME/workspaces`, including paths reached through
symlinked parents. Missing, incorrectly owned, writable, or private-workspace
configuration makes the Demo unavailable.

T22.2 adds identity, API access checks, invitation administration, and the
minimal access UI. Gate A provisions a durable private workspace for each
authorized Google subject. The internal workspace ID is random and server
generated; the email is used only by authentication authorization and never to
choose storage. The workspace root defaults to
`$SIGMA_CLOUD_AUTH_HOME/workspaces`; set `SIGMA_CLOUD_WORKSPACES_ROOT` to an
absolute private directory to place it elsewhere. Each workspace contains that
user's `.sigma` projects and `.sigma-state` Recent index. It is not prefilled
with local projects or sample copies. The curated Samples catalog remains a
shared read-only source; opening a sample makes a separate copy in the user's
workspace.

There is no automatic import or migration from local projects. To bring an
existing project into a cloud account, its owner must first use the existing
Project Audit export contract and a separately authorized import path; Gate A
does not add cloud import. No administrator route provides access to another
user's project contents. Revoking authorization denies future requests but
retains the workspace and its data for possible later reauthorization.

Back up both the cloud auth database directory and the workspace root as one
consistent recovery point, with SIGMA stopped so no SQLite/project write is in
flight. Keep the backup encrypted and access-controlled like the source. Restore
the directories to their configured paths with service ownership, mode `0700`
on directories, and mode `0600` on SQLite files. Start SIGMA and verify that
two authorized test subjects still see only their own Recents and artifacts.
The deterministic `tests/cloud_workspaces.py` test exercises an offline copy
and restore of the workspace root, including its subject mapping, projects,
Recent indices, execution records, and artifact bytes. The auth database is a
separate backup component because it stores authorization and sessions.

Gate A does not implement durable job scheduling, anonymous Demo APIs, or cloud
deployment. Cloudflare feasibility and deployment remain separate from this
authentication and filesystem-backed workspace implementation.

## Gate B research execution configuration

Cloud research inference is enabled only when an operator explicitly supplies
`SIGMA_CLOUD_OPENAI_API_KEY`, `SIGMA_CLOUD_USER_SPEND_CEILING_USD`, and
`SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD`. Initial pilot values are `$2.00` per
verified Google subject and `$15.00` globally. The five initial invited
accounts (including the administrator) start with `$2.00` each, leaving `$5.00`
under the global ceiling for operator-directed testing and unresolved charges.
The default allowance is configurable from `$0.01` through `$15.00`; an
administrator can set a per-entry USD allowance in Access Management up to the
global ceiling. An exact email rule overrides its matching domain rule. Domain
allowances apply independently to each verified user's subject-backed
workspace, never as a shared pool. The user's allowance is cumulative, does not
reset automatically, and follows the stable verified subject across changed
email addresses, sign-out, revocation, and new projects. The administrator has
no spending exception. Lowering an allowance below recorded spend preserves
all estimated and unknown charges and blocks further inference until the
effective allowance again exceeds recorded spend. Cloud
mode never falls back to a checkout's `OPENAI_API_KEY` or a locally connected
ChatGPT plan. The service credential stays in the backend environment; the
cloud UI cannot read, replace, or select it. Keep the deployment's secret
store and backups access-controlled, and rotate the key through the operator's
secret-management process.

Each call atomically reserves a conservative maximum cost against the
authenticated user's remaining allowance and the global ceiling before
dispatch.
Confirmed provider token counts are priced using SIGMA's reviewed model price
table; the reported cost remains an estimate. If a call times out, is canceled,
or its response is lost before its usage is saved, the full reservation remains
held and the attempt is recorded as unknown. Such a call is never automatically
retried. Cloud sessions are capped at `$0.25` estimated cost, six model calls,
and 15 minutes regardless of larger saved project limits. A priced model and
explicit token usage bounds are required. The ChatGPT connection dialog reports
the authenticated owner's read-only allowance, estimated usage, held
reservations (including unknown charges), and remaining allowance. Exhaustion
blocks new inference while saved projects and research remain readable.

The service ledger also enforces these environment-configurable limits:

| Variable | Default | Meaning |
|---|---:|---|
| `SIGMA_CLOUD_USER_MAX_CONCURRENT` | `1` | Running sessions per workspace |
| `SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT` | `2` | Running sessions across the service |
| `SIGMA_CLOUD_USER_MAX_QUEUED` | `2` | Queued sessions per workspace |
| `SIGMA_CLOUD_GLOBAL_MAX_QUEUED` | `16` | Queued sessions across the service |
| `SIGMA_CLOUD_USER_TOKEN_BUDGET` | `2000000` | Reserved or observed model tokens per workspace |

Malformed or missing user or global spend configuration disables cloud
research; configured default user allowance and individual entries are limited
to `$15.00`, as is the global ceiling. Spend totals include completed estimates, live reservations, and
unknown provider outcomes. A reservation is released only when the provider
call is proven not to have been dispatched; age, restart, timeout, cancellation,
and account revocation do not release uncertain charges. Accounting is shared
across the user's projects and persists in the SQLite ledger. Queue slots,
active slots, provider attempts, token reservations and spend reservations
are stored in `cloud-research.sqlite3` beside the workspace mapping database,
under the configured private workspaces root. Back up that file together with
the auth database and workspace tree. The existing project session records
remain the source of truth for events, checkpoints, call outputs, computation
runs, and outcomes. Steps retain their role, strategy, cycle, and source-artifact
references; raw full prompts are not persisted. Queued sessions with no provider
attempt and a saved session record can be picked up when the owner reconnects
after restart. A prior-process queued ledger row is removed only when recovery
holds the project admission lock and proves the project still matches, the
session record is absent, and no provider-call rows exist. This recovers a crash
between queue reservation and session publication without using row age. Missing
or unsafe metadata, valid session records, running jobs and every call
reservation are preserved. Claimed work is reconciled to paused/interrupted
with an unknown attempt; it is not replayed.

The shared cloud key is deliberately restricted to bounded research sessions.
Standalone proposal, agentic-proposal, paper-generation, and text-conversion
inference routes return 403 in cloud mode until they receive their own durable
budget accounting. Local mode keeps the existing provider selection and routes.

Automated tests use local RSA signing keys and mocked Google endpoints. They do
not make network requests or paid model calls. No Google OAuth client, client
secret, allowed organization domain, or admin email is hardcoded in source.


---

# Part 4: Hosting decision history


Status: COORDINATOR RECOMMENDATION, not approved infrastructure provisioning or proof of hosted security.
Date: 2026-10-23.
Parent: [T22.3](../tickets/t22.3.md); scientific feasibility [T22.1 spike](https://github.com/bkramerext/sigma/blob/07a76ac21a2eb92ba85388950a83de55821ca17b/cloud-spike/README.md).

## Updated recommendation: Google Cloud Free Trial for a temporary alpha (2026-10-23)

**Preferred trial option, subject to human confirmation of eligibility, exact Google Cloud estimate, and authorization:** Google Cloud Compute Engine `e2-standard-2` (2 vCPU, 8 GiB RAM) in Oregon `us-west1`, Ubuntu Linux, normal Docker Engine and separate bounded scientific containers, one HTTPS reverse proxy serving the compiled frontend and FastAPI on the same origin, standard persistent disk holding all SIGMA cloud service state. Do **not** deploy using deprecated `create-with-container` or `gce-container-declaration` machinery. Use ordinary OS package installation or cloud-init with managed services. No GPUs or Marketplace images. A single VM avoids a Cloudflare Worker/D1/R2 persistence migration.

**Reason:** The user's objective is a short-lived external evaluation, not permanent production service. The Google Cloud **$300 over 90 days** welcome credit is a better initial economic fit if the account has never previously enrolled and meets Google's other eligibility requirements. The trial applies to Compute Engine usage, and does not automatically upgrade to paid billing. Google may stop and eventually delete resources if the trial ends unupgraded; export worthwhile evaluation data before expiry. OpenAI API/model charges are **external and not covered** by this trial.

**IMPORTANT cost qualification:** The free `e2-micro` (about 1 GiB shared memory) does not supply comfortable SIGMA/Docker/Sage capacity. An `e2-standard-2` is a *billable* 8-GiB VM covered by trial credits, not an Always Free entitlement. VM, 30–60 GiB persistent boot/data disk, public external IPv4 address and network egress all consume credit. Google currently charges $0.005/hour for an in-use standard VM external IPv4 (~$3.65 per 730-hour month), apart from VM and disk charges. **Get the actual `us-west1` all-in Compute Engine pricing-calculator estimate before provisioning.** Do not assume $300 pays for 90 days of continuous `e2-standard-2` hosting; allow for a shorter evaluation window or deliberate smaller VM after measured load. Suggested planning threshold: keep projected 90-day credit consumption comfortably under $300, alert at $100/$180/$240 and plan shutdown or export before depletion. These are operator alerts, not a guarantee against all credit consumption.

**Cloudflare compatibility:** Current T22/T22.3 make Cloudflare edge hosting a release requirement. This recommendation proposes **deferring Cloudflare for the initial Google-hosted controlled alpha** if the human explicitly approves an amendment to that requirement. A GCP-hosted VM can serve HTTPS with a domain and Caddy/nginx/Let's Encrypt, or behind a Cloudflare Free proxy with a domain already owned. A purchased custom domain or Google load balancer is not required merely to prove Python deployment. However, Google OAuth's exact HTTPS callback/public origin, the secure `__Host-` cookies, and static/frontend same-origin API routing require a tested public hostname and certificate. **Do not call GCP-only hosting T22 accepted before the Cloudflare requirement is explicitly resolved.**

### GCP deployment proof plan (no cloud services provisioned yet)

1. Confirm eligible **non-billable** Free Trial account with remaining credit and 90-day window; check `us-west1` E2 CPU/disk quota and machine capacity (Free Trial cannot request quota increases). Keep paid-account upgrade **disabled**.
2. Price the **specific** `e2-standard-2` + persistent disk size/type + external IPv4 + estimated transfer for Oregon using Google Cloud's calculator. Reject unaffordable configurations; no automatic paid-account upgrade. Check whether preexisting domain can host TLS, or document a reversible trial HTTPS endpoint.
3. Provision a single Ubuntu VM with least privilege; set host firewall to public 443 only (plus tightly restricted administration), restrict the FastAPI and Docker sockets to internal loopback/trusted service accounts; remove any direct public API or database exposure. Set OS patching and service restart policy.
4. Deploy the compiled frontend, the FastAPI service and its Google OAuth routes through the **same exact HTTPS origin**. Test session cookie, CSRF/Origin, TrustedHost and Google redirect URL with real hosted browser; don't rely on local Vite.
5. Mount durable VM persistent storage with strict ownership, stable paths and versioned service migration. Keep auth mappings, all private projects, project-session JSON, artifacts, and Gate B SQLite job/call reservation ledger consistent across process restart, VM reboot and application redeploy. Alpha backups intentionally deferred to T22.4. Export user data manually before trial expires if worth keeping.
6. Validate scientific Python/Sage Docker containers on this **real GCP VM**, with network disabled, no mounted host secrets/daemon/socket/private project data, non-root, resource/time/process limits and bounded parallelism. Do not enable scientific tools to external users if isolation or host memory checks fail. This is a mandatory T22 gate, not a reason to weaken it.
7. Run a controlled pilot with two authorized Google identities, denied/anonymous Demo, revoked user and adversarial cross-workspace APIs. Test durable research disconnect, queued/restart recovery, double starts, budgets/ambiguous provider calls, exports, guest non-mutation and local regression. Deterministic fake provider only until separate paid API approval.
8. Monitor credit burn and resource usage; document actual spend, date/time and remaining credit. Before trial ends, either export retained research and tear down all billable resources or obtain **separate explicit** authorization for paid migration. No implicit conversion.

**Official technical sources, checked 2026-10-23:**
- Trial coverage, restrictions, eligibility and expiry: https://docs.cloud.google.com/free/docs/free-cloud-features
- 2vCPU/8GiB E2 type and limits: https://docs.cloud.google.com/compute/docs/general-purpose-machines
- Docker on ordinary Compute Engine Linux VM: https://docs.cloud.google.com/compute/docs/containers
- Free-trial quotas: https://docs.cloud.google.com/compute/resource-usage
- In-use external IPv4 $0.005/hour: https://cloud.google.com/vpc/pricing
- Detailed GCP pricing estimator: https://cloud.google.com/products/calculator

**Disposition:** Feasible architecture established from product documentation and SIGMA's known FastAPI/Python/SQLite/Docker design; actual hosted build, required account/quota, security boundary, exact price, OAuth certificate/domain and full integration **UNVERIFIED**. No resources created or paid. Red owns deployment implementation; Green owns Gate B; coordinator owns decision/ticket and acceptance reviews.

---

## Previous VPS decision (fallback, not current recommendation)

**Budget correction (human, 2026-10-23): target approximately $5/month, do not authorize $48/month hosting.** Prefer a low-cost evaluation deployment, with Cloudflare Free DNS/HTTPS proxy and a small conventional Linux VPS if necessary. Test memory, CPU and isolation before sizing up. The earlier 4-vCPU/8-GiB suggestion is a capacity-upgrade option only, not the approved baseline. Serve the compiled React SPA and `/api/*` from one hostname via trusted reverse proxy on the VM. FastAPI, local file-backed user projects and the SQLite auth/workspace/job ledgers share one mounted persistent host filesystem, while scientific code executes in separate bounded Docker containers. Do not rewrite Python into Workers or D1 merely to deploy.

This is a smaller initial service architecture than introducing Cloudflare Workers, Pages, D1 and R2 together. For the low-cost conventional-host alternative the Cloudflare contribution is the Free edge proxy/DNS/TLS; the Python backend and persisted state run on conventional infrastructure. The architecture honors T22.1's recommendation of a conventional sandbox host because remote Cloudflare scientific isolation has not passed its gate.

**Important:** A Cloudflare-managed hostname in front of this conventional VM requires an owned domain added to Cloudflare DNS. A Cloudflare account is free, but domain registration may not be. A temporary host-only HTTPS endpoint can be used for a controlled non-Cloudflare smoke test, and an alternate workers.dev proxy may be evaluated only if necessary. Neither substitute should be misreported as final Cloudflare edge deployment. Cloudflare Tunnel also requires a domain for published applications. Cloudflare Workers Paid is not required for this recommendation.

## Candidate sizing and verified rate card

| Component | Initial candidate | Published baseline | Qualification |
| --- | --- | --- | --- |
| Cloudflare DNS/proxy/SSL | Free plan | $0/month | Valid owned-domain setup, subject to Free plan features and fair use |
| Lowest-cost conventional VM candidate | DigitalOcean 1 vCPU / 1 GiB RAM / 25 GiB SSD | $6/month | Near the budget, but scientific Docker/Sage and concurrent research capacity are unverified and likely highly constrained |
| Low-cost VM alternative | DigitalOcean 1 vCPU / 2 GiB RAM / 50 GiB SSD | $12/month | Candidate for serial research work, subject to measured memory and host isolation |
| Optional capacity upgrades | DigitalOcean 2 vCPU / 4 GiB at $24 or 4 vCPU / 8 GiB at $48 | $24–48/month | NOT approved as alpha default; require actual measurements and explicit human budget approval |
| Cloudflare native container experiment | Workers Paid base with included container usage | $5/month base plus measured usage | Non-durable container local storage and Python/Sage isolation remain blockers; cannot claim whole SIGMA costs only $5 |
| Domain | Existing domain/subdomain, preferred | $0 incremental if already owned | New domain registration/renewal is extra and varies by TLD/registrar |
| Google OAuth | Existing user Google identity and new OAuth client configuration | No app-hosting line-item assumed | Verify provider limits and configuration at deployment; no Google Workspace purchase required by T22 |
| Provider inference | Explicit server-side API credential only | Usage-dependent, with a hard SIGMA ceiling | Not included in VM baseline; never use ChatGPT subscription as automatic cloud credential |
| Optional snapshot/backup | Deferred to T22.4 | Not included | No off-host recovery claim for external-evaluation alpha |

**Budget requirement:** aim for $5/month total platform baseline. The cheapest published DigitalOcean conventional VM is $6/month, not $5; a 2-GiB VM is $12/month. Cloudflare Workers Paid is $5/month *base* with finite container memory/CPU/disk inclusions and potential overages; not a guarantee of $5 all-in. An existing domain may avoid new registration, and Cloudflare Free proxy adds $0. A strictly $5 cap may require Cloudflare-only non-scientific/limited-mode hosting or another carefully tested free/low-cost provider. Do not buy any service before the human approves the actual amount. A modest VM with research concurrency limited to one and SageMath disabled until safe measured hosting is acceptable only if this restriction is explicitly documented and separately approved against T22 alpha requirements. Platform hosting and model inference remain separate budgets. Stop unused billed resources; VM charges may continue while idle.

Sources checked October 23, 2026:
- Cloudflare Free features and TLS: https://www.cloudflare.com/plans/
- Cloudflare domain prerequisites: https://developers.cloudflare.com/learning-paths/clientless-access/initial-setup/add-site/
- Cloudflare DNS origin mapping: https://developers.cloudflare.com/dns/manage-dns-records/how-to/create-zone-apex/
- DigitalOcean current Basic Droplet rate card (includes $6/1GiB and $12/2GiB): https://www.digitalocean.com/pricing/droplets
- Cloudflare Workers Paid and Container usage inclusions, $5 base plus metered charges: https://developers.cloudflare.com/containers/platform/pricing/
- Earlier SIGMA scientific feasibility: PR #22 merged to the T22.1 **feature branch** (not verified as part of main), at https://github.com/bkramerext/sigma/pull/22 and the pinned spike link above.

## Required technical validations before public alpha

1. **Single origin:** User browser visits `https://<approved-domain>/`; SPA/static files and `/api/*` resolve on the exact origin. Google OAuth callback uses `https://<approved-domain>/api/cloud-auth/callback`. Do not ship with hardcoded localhost or public VM IP in OAuth/JS. Ensure WebSocket/SSE or polling used by SIGMA works through the proxy without losing durable job status.
2. **TLS end to end:** Cloudflare HTTPS at edge, validated encrypted origin connection (Full Strict or equivalent); secure `__Host-` session cookies, correct trusted-host/origin checks, no insecure HTTP application exposure. Permit only necessary network ports. No bypass that exposes raw FastAPI/admin ports publicly.
3. **Durable state:** Auth mapping, user workspaces, project JSON, research ledger, attempts, artifacts and audit logs on stable disk paths; normal restart/redeploy/rollback must not replace or overwrite these. The alpha deliberately does **not** include off-host backup/restore; record potential permanent loss on volume failure.
4. **Compute isolation:** API process is not root; generated code has no network, secrets, auth database, Docker socket or host project mounts. Verify real host Docker behavior and restricted runner boundary. Raw Docker daemon control granted to an untrusted FastAPI process is unacceptable. Do not enable hosted Python/Sage until this passes; if not safe, disable sandbox actions rather than silently weakening isolation.
5. **Concurrency/cost:** Size host for actually tested sandbox processes, not theoretical vCPU count. Configure initially one concurrent scientific sandbox and a small global agent-run limit, then increase after measured multiuser load. Host resource exhaustion must fail closed with recoverable UI error.
6. **Auth and guest:** Verified Google login, owner/denied/admin access, immediate revocation, public immutable Demo, direct API mutation denial, safe exports, and no cross-tenant leakage tested through the real deployed HTTPS endpoint. No broad temporary gmail.com authorization before external demo.
7. **Operations:** Reproducible deployments, pinned images/software, least-privilege Cloudflare tokens, service restarts, alert/health, logs without secrets, state-preserving rollback and kill switch for inference.
8. **Real acceptance:** Distinguish mock-provider in actual hosted backend from UI-mocked APIs, Cloudflare edge checks, independent CI, and paid live-provider smoke. No inference usage until explicit authorization.

## Human authorization checklist, before money or live changes

- [ ] Confirm there is an existing domain/subdomain to use; otherwise explicitly approve new domain registration and renewal price. Do not assume domain purchase is authorized.
- [ ] Approve the Cloudflare account and adding/changing the chosen domain's DNS; confirm nameserver change will not disrupt other websites/email.
- [ ] Approve hosting account/payment, region, measured VM/container capacity and a strict maximum recurring spend. The previously proposed $48/month VM has NOT been approved and must not be provisioned. Provisioning is a distinct action requiring approval.
- [ ] Register Google OAuth client and add the exact approved production origin/redirect URI. Supply secrets directly through the host's secret store, never chat/repository.
- [ ] Configure initial administrator address via deployment secret and invite rules, plus a conservative server-side provider-spend ceiling; live model key and usage require separate approval.
- [ ] Review the hosted security/integration acceptance evidence and approve external publication independently of earlier paid infrastructure approval.

## Sequence

**Now:** Red continues existing T22.3 deployment implementation, Green closes Gate B ledger recovery. This document is only coordinator-owned planning and must not be interpreted as a change dispatched to either worker.

**After PR review:** Integrate Gate B and Red's deployment scripts, run complete regression; decide whether actual host architecture remains feasible from Red's measured evidence. If Red has implemented a defensible different hybrid, compare it before altering worker ownership.

**Then:** Present approval checklist and exact expected cost; user supplies accounts/billing/permissions through provider UIs; conduct controlled deployment, multi-browser integration and security acceptance. Public release requires explicit human signoff.

## Alternatives and rejection rationale

- Cloudflare Worker + D1/R2: valuable later, but requires new persistence and/or execution adapters while Python and POSIX locking already function on a conventional VM.
- Cloudflare Workers Containers: cloud-native scientific execution isolation unverified; latest T22.1 spike explicitly chose conventional sandbox fallback.
- Cloudflare Pages separate from API host: possible, but cross-origin OAuth/cookie/CSRF and proxy routing increases first-alpha complexity. A same-origin VM frontend behind Cloudflare is simpler.
- Cloudflare Tunnel from user's Mac: not an independently hosted service and requires the home Mac to stay online.
- Fly.io hosted machine plus volume: viable competing platform, but container execution, volumes and safe sandbox daemon ownership still require verification; a plain Linux host makes current Docker behavior more directly reproducible.

## Outstanding unknowns

Domain ownership, billing approvals, Cloudflare account creation, target VM/region, live Google OAuth configuration, deployment secrets, tested resource profile with Python/Sage, actual sandbox boundary, hosted integration and full cost are **UNVERIFIED**. Nothing in this document constitutes a deployed service.


---

# Part 5: External-host feasibility notes


**Status:** Planning only. Not an implementation assignment or an authorization to change SIGMA's architecture.
**Date:** October 21, 2026

## Purpose and guiding constraint

Make SIGMA accessible to a small number of outside users as a **genuine, interactive, polished research showcase**, while retaining a useful locally running application. The intended audience includes people evaluating the product and engineering approach, particularly Onebrief. This is not a plan to launch a production SaaS business.

**Design test:** Does a decision make the demonstration more compelling, trustworthy during ordinary use, or simpler to deliver? If not, defer it. Showcase quality is not the same as production infrastructure complexity. We should spend effort on a pleasing experience and avoid preventable loss of users' specifications, strategies, or results.

Do not begin implementation until this plan is revisited and a specific assignment is approved. Reinspect the then-current repository; the notes below describe the October 21 baseline.

## Scope and priorities

| Concern | Position |
| --- | --- |
| Working hosted application | **Required.** Read-only demos are explicitly out of scope. |
| Local SIGMA | **Required.** Continue to run locally with local persistent storage; filesystem or SQLite is acceptable. |
| A few concurrent visitors | **Required.** Good interactions, independent workspaces, no lost edits. |
| User identification and private investigations | **Required for hosted use.** Minimal sign-in, ownership and server-side authorization. |
| AI proposals | **Required.** Prefer visitors' own ChatGPT accounts if supported and eligible, without charging the SIGMA owner unexpectedly. |
| Clear privacy policy | **Required.** Persistent, unobtrusive lower-right Home link; publicly readable page. |
| Data portability / export-import | **Non-goal.** Do not build it merely to satisfy conventional SaaS expectations. |
| Production-grade operations / availability | **Non-goal.** No elaborate disaster recovery, observability stack, or multi-region design. |
| Long-running autonomous investigations | **Undecided.** Don't build a durable agent orchestration system until the demonstration requires it. |
| Large-scale multi-tenancy, collaboration, public editing | **Non-goals for first hosted release.** |
| Preservation of approved UI artwork | **Required.** No unrequested Home redesign. |

Reliability is a non-goal in the *operational platform* sense, not permission to lose user work. Persistence, transactional integrity, understandable error states, and safe retry behavior remain requirements.

## Two operating modes

### Local mode

`./sigma ui` should remain a first-class experience. Investigations, strategies, and history live on the user's machine. The current implementation uses per-project JSON files and filesystem locking. A future switch to local SQLite is an **option**, not a prerequisite; it is attractive only if it materially reduces divergence between local and hosted code. Do not force a cloud account for local manual research.

### Hosted mode

A visitor reaches SIGMA through a normal HTTPS URL. They can browse included public examples, sign in, create an investigation, edit strategies, use AI where authorized, and return to their own work later. Persistent research data is stored in the cloud, not on the developer's Mac. Cloudflare is the preferred infrastructure to evaluate, not a commitment to a particular database or execution runtime.

**Cloudflare Tunnel** is an expedient way to expose the locally running *full* application for a controlled demonstration. It is not the same as an independently hosted application: the Mac must remain online, and multi-user data separation and public authentication would still need attention. A static read-only frontend is not an acceptable substitute.

## Hosted user experience

### Home

Preserve SIGMA's existing approved Home artwork and visual identity. Retain the existing prominent New/Open affordances; do not clutter the entrance with account and infrastructure controls.

- **New Investigation** (currently called **New Project**) creates an investigation owned by the signed-in user, private by default. If a visitor is not signed in, request sign-in at the point of action and resume the intended action without discarding entered information.
- **Open Investigation** lists the user's own investigations, any explicitly shared ones if that feature later exists, and public examples. It does not ask hosted users to type a local filesystem path.
- **Recent Investigations** shows the user's own recent activity, subject to the existing compact Home layout; another visitor's private work never appears.
- **Explore examples** allows visitors to inspect included sample investigations. A future **Fork** action could make an editable private copy, but public browsing/forking must not silently mutate a shared canonical sample.
- **Account identity** should be discreet. A sign-out option and clear current-account indication are sufficient initially.
- **Privacy Policy** is a persistent small link at the **lower-right corner of Home**, visible before sign-in, opening a dedicated readable page.

The potential rename from **Project** to **Investigation** is a separate product decision; use existing UI vocabulary until explicitly approved. Avoid redesigning the UI as part of a hosting assignment.

### Ownership and sharing

Do **not** put everyone in a single shared editable project collection. The initial hosted model is individual private investigations plus a small curated public example library. Public examples should be protected against visitor edits. Publishing, invitations, collaborative editing, moderation, and community contribution workflows are later possibilities, not current scope.

One shared database for multiple users is fine. Isolation is logical and enforced by the backend, not by separate databases or hidden frontend controls. Every read and mutation must resolve the authenticated principal and check ownership/visibility. A project UUID is not authorization.

## Identity and AI access: separate responsibilities

**SIGMA identity** answers who owns the investigation. **AI authorization** answers whose allowance or bill pays for an inference. They must not be conflated.

Prefer a minimal social sign-in rather than building passwords. Google or GitHub identity are practical fallback options; using ChatGPT sign-in as the single identity would be even more frictionless **only if the supported hosted OAuth program permits it and yields a stable, verified identity suitable for SIGMA accounts**. This is unresolved and must be verified before choosing the login design.

The existing Sign in with ChatGPT flow was implemented for an open-source **locally hosted** application, with loopback authorization and local credential storage. Do not assume its client registration, redirect behavior, terms, token-sharing permissions, or model allowances transfer unchanged to a publicly hosted site. Specifically verify:

1. Whether public hosted SIGMA is eligible for a supported Sign in with ChatGPT integration and what registration, redirect URI, client type, and security requirements apply.
2. Whether ChatGPT **Free** accounts can authorize this use, which models/features they can use, and how rate/credit exhaustion is surfaced. No claim of guaranteed free inference without verification.
3. Whether the identity scopes and verified subject can be used for SIGMA user accounts, or whether a separate Google/GitHub sign-in is necessary.
4. Whether the resulting tokens are tied to the individual signed-in visitor and can be safely stored/used server-side in a hosted multi-user environment.
5. What the user sees on disconnect, expired credentials, unsupported accounts, exhausted limits, and temporary network failures.

Retain explicit API-key billing as an optional separate mode if appropriate. **Never silently fall back to a key paid for by the application owner.** Do not expose provider tokens to other users or to browser JavaScript. Protect any server-stored tokens and OAuth session state, and ensure account switching cannot attach a response to the wrong user's investigation.

**Go/no-go dependency:** Public-hosted ChatGPT authorization is the biggest unresolved product assumption. Test it with an actual Free account before promising visitors that experience. If unavailable, decide explicitly whether separately billed API access or a limited demonstration is acceptable; do not quietly change the economics.

## Persistence and Python domain model

The existing research concepts—investigations, strategies, ordered active strategies, immutable-ish history/events, model settings and proposal review—should remain Python domain objects independent of storage. Prefer a small, explicit persistence boundary so local and hosted execution share business rules.

Conceptual operations (illustrative, not a prescribed class API):

```python
create_investigation(owner_id, draft)
get_investigation(principal, investigation_id)
list_investigations(principal)
save_investigation(principal, investigation_id, expected_revision, changes)
record_event(principal, investigation_id, event)
```

**Cloud storage candidate:** One Cloudflare **D1** database for users, investigations, strategies and event history; **R2** only if artifacts grow beyond ordinary structured data. D1 is SQLite-compatible at the SQL level but is not a local `sqlite3` file accessible to an arbitrary FastAPI process. Its binding/HTTP interfaces, transaction limitations, deployment model and concurrency semantics must be assessed before settling on it.

**ORM choice depends on runtime:**

- If Python/FastAPI runs on a conventional server or container with PostgreSQL, SQLAlchemy 2.x is a reasonable mature ORM.
- If we choose Cloudflare D1, a focused SQL repository using its supported access mechanism may be simpler than forcing SQLAlchemy's ordinary SQLite dialect over an incompatible connection.
- If local SQLite simplifies the codebase, use it deliberately, but do not mistake SQL compatibility for interchangeable D1 and local connection/transaction APIs.

Do not prematurely rewrite the current JSON persistence merely to align with an undecided cloud platform. Compare a minimal D1 adapter with a conventional hosted Python + relational database solution based on implementation effort and demonstration experience.

A provisional hosted schema might contain `users`, `investigations` (owner, visibility, revision), `strategies`, and `events`; actual normalization and migrations should follow the current domain invariants. Public sample investigations should be seeded idempotently and never overwrite visitor edits or personal copies.

## Concurrency and protecting research work

This is a **must-have**, even for a handful of users. A pleasing demo cannot silently discard a visitor's specification, strategy, or AI output.

- Give each investigation a monotonically increasing **revision** or equivalent optimistic-concurrency token. Mutations include the version the editor read. Reject a stale write with a clear conflict response rather than overwriting newer work.
- Commit each logical mutation and its associated history/event **atomically**. A partial strategy save with missing history, or vice versa, is not acceptable.
- Enforce identity/ownership on the server for reads, updates, deletes, history and AI-related persistence. Test direct API access across two accounts.
- Protect against two tabs editing the same investigation, simultaneous AI proposal completion, repeated submissions, and browser/network retries. Where operations can be repeated, use idempotency or a well-defined duplicate policy.
- Keep **draft generation separate from explicit save**, as SIGMA does today. An AI response must not silently replace user-authored work. Preserve an unsaved draft across authentication interruptions where feasible.
- Surface conflicts with a clear recovery path that preserves the user's pending text. Avoid making visitors understand database revisions or manually reconcile JSON.
- A failed network request must not claim a save succeeded; conversely, an acknowledged successful save must survive reload and reopening.

For D1 specifically, verify that the chosen mutation pattern can enforce the revision check and required atomic writes under its actual transaction model. Do not rely on read-then-write without a concurrency guarantee.

## Hosting architecture candidates

**Candidate A: Cloudflare-hosted frontend + suitable Python backend + database.** Minimal change to Python business logic, but involves operating a small Python server/container and connecting to storage. Could be simplest engineering route even if the infrastructure bill is somewhat higher.

**Candidate B: Cloudflare frontend + Workers-based API + D1.** Consolidates infrastructure but may require substantial changes to FastAPI/Python runtime assumptions, file APIs, locking, local loopback OAuth, and background execution. Do not estimate this as a mere deployment configuration change.

**Candidate C: Cloudflare Tunnel to local full-stack SIGMA.** Fastest controlled hands-on access; no independent cloud persistence. Useful for an early demonstration, but not equivalent to hosted multi-user SIGMA.

The Vite development proxy currently targets localhost, and `./sigma ui` manages local processes. Hosted mode needs production static asset serving, HTTPS routing, allowed origins, safe cookie/session behavior, and server-side API configuration. The local launcher should not be broken in the process.

**Selection criterion:** lowest implementation complexity that provides authentic interactive use, correct ownership, safe writes and good AI access for a few visitors. No requirement to use Cloudflare for every component.

## Privacy policy and data handling

Place the unobtrusive **Privacy Policy** link at Home's lower-right, without changing approved artwork. The policy should state what the actual deployed system does, not promise unimplemented protections.

Cover, in ordinary language:

- What account identity information is retained and why.
- What investigation data is stored: problem statements, strategies, edits, events/history, model preferences, AI-generated proposals **when saved**, and any future artifacts.
- Which data is transmitted to OpenAI during an AI request, and how OpenAI's handling differs from SIGMA's own storage.
- Whether authorization tokens are stored, their purpose, and how disconnection works.
- Private-by-default ownership and the exact behavior of public examples or any later sharing.
- How long data is kept and what deletion does **as implemented**; don't promise export, guaranteed erasure windows, or backup deletion procedures that do not exist.
- Basic access/security measures and a real operator contact route when one is available.

Do not claim zero retention, encryption at rest, regulatory compliance, or AI-provider training exclusions without validating the actual configuration and policies. The privacy page must be readable without logging in. An appropriate review of the final public policy is advisable before opening the site to others.

## Long-running investigations: decision deferred

Today's AI interaction is human-guided strategy generation with explicit review/save. That is enough for the first hosted demo unless the product narrative changes. Long-running, multi-agent research may eventually require queued execution, durable checkpoints, budgets, cancellation, isolation and progress reporting. Do **not** implement that system now or impose its abstractions on simple proposal generation.

Avoid painting ourselves into an obvious corner: keep research state and AI invocation reasonably separate, and avoid assuming an HTTP request can run forever. Beyond that, wait for a concrete demonstration use case.

## Costs and effort: preliminary only

Cloudflare's entry-level Workers/D1/R2 pricing may make a light-traffic deployment inexpensive, but **the cheapest Cloudflare bill is not necessarily the cheapest engineering architecture**. A conventional Python backend may add server cost and save implementation time. Domain, authentication provider, database operations and storage can add charges; AI inference is a separate and potentially dominant cost. Recheck current pricing and free-tier allowances when implementation is scheduled.

Working estimates, highly dependent on the chosen architecture and auth feasibility:

| Deliverable | Rough engineering effort |
| --- | --- |
| Controlled, authenticated full-app Tunnel demonstration | ~1–2 days, after checking existing local-app security assumptions |
| Small hosted single-owner interactive deployment | ~3–6 days if existing Python backend can largely be retained |
| Hosted few-user experience with identity, ownership, safe concurrent writes, privacy page and tested AI connection | ~2–4 weeks, potentially more if public ChatGPT sign-in is unavailable or runtime migration is substantial |

These are planning ranges, not commitments. They do not include building autonomous agents or production SaaS operations. Avoid presenting a precise monthly total until the backend/runtime and inference model are chosen.

## Risks and concrete discriminating tests

1. **Hosted ChatGPT authorization:** Run a minimal, documented hosted OAuth proof of concept, including a Free account, account switching, expiry, and exhausted allowance. Failure may change the demo's economics or login UX.
2. **D1 transaction semantics:** Implement a tiny two-writer revision-checked update with event insertion; verify exactly one competing write succeeds and the loser retains its draft.
3. **Python runtime fit:** Prove the selected hosting option supports the current backend's required dependencies, response streaming, OAuth callbacks, and reasonable request lifetimes without a major rewrite.
4. **Multi-user isolation:** Two test accounts create investigations; verify no cross-account list, read, edit, or AI-result association is possible, including direct API calls.
5. **Experience test:** Real browser checks for New/Open/Recents, login interruption and resume, AI proposal/review/save, refresh/reopen, two-tab conflicts, and small-screen layout. Verify original Home artwork remains unchanged.
6. **Local regression:** `./sigma setup`, `./sigma test`, `./sigma ui`, and existing local projects must continue to work. Cloud hosting cannot become a prerequisite for local manual research.

## Decisions intentionally left open

- Is the first outside demo a controlled Tunnel, or a genuinely independent cloud deployment?
- Is SIGMA identity provided by ChatGPT, Google/GitHub, or a small combination?
- Can Free ChatGPT accounts use a supported hosted authorization flow for SIGMA?
- Does the Python backend stay on a conventional server, or is a Workers-compatible API worth the migration?
- Is a shared local/cloud SQL domain persistence layer simpler than preserving local JSON plus a cloud adapter?
- Do we need Fork for the first demo, or only a safe way to start from curated examples?
- Is there a concrete long-running investigation experience worth demonstrating?
- When, if ever, should UI terminology change from Project to Investigation?

**Do not turn open questions into hidden assumptions or implementation gates.** Return to them when a specific external-hosting assignment is commissioned.

## Suggested implementation sequence when resumed

1. Verify hosted ChatGPT authorization and Free-account behavior; make an explicit decision on identity and billing.
2. Select the smallest viable backend/database arrangement using a thin concurrency/transaction proof of concept.
3. Implement per-user authentication/ownership and safe, revision-checked persistence without disturbing local SIGMA.
4. Adapt hosted New/Open/Recents and public sample behavior; preserve the existing visual design.
5. Add the truthful public Privacy Policy page and lower-right Home link.
6. Run a small, real-browser, two-account end-to-end demo with concurrent edits and actual AI use.
7. Stop when the showcase is convincing. Do not add portability, production operations or autonomous orchestration by inertia.

The central requirement is simple: **a handful of visitors should be able to use SIGMA as a real research tool, enjoy the experience, and trust that their work won't disappear.**
