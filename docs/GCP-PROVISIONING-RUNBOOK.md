# SIGMA Google Cloud provisioning runbook

This runbook turns the approved Compute Engine plan in
[GCP-DEPLOYMENT.md](GCP-DEPLOYMENT.md) into staged operator commands. It does
not authorize resource creation. The commands below are for one `us-west1` VM
and require review and explicit approval by the project and billing owners.
Do not paste secrets into shell commands, GitHub, chat, or source control.

## Provisioning can start before a domain is selected

The VM, persistent disks, VPC, IAP-only administration path, and reserved
regional static IPv4 address do not require a domain or production OAuth
client. Reserve the static address and attach it to the VM now; keep web
firewall ingress closed while the VM is prepared. Record the address. It can
be used when a domain is selected later.

Do not start the SIGMA Compose stack yet. `deploy/compose.yaml` requires
`SIGMA_DOMAIN`, a production Google OAuth client ID, secret files, and the
rootless sandbox socket. Caddy obtains a public certificate for the domain.
Before domain selection, provision and harden the VM, mount the state disk,
install Docker, stage the reviewed release, build the pinned images, and
validate the VM privately through IAP/SSH and local health requests. Do not
open TCP 80/443 or configure Caddy publicly until DNS, OAuth, secrets, and the
production domain are approved.

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
- Domain selection is deliberately deferred. Domain registrar purchase and
  renewal are outside this estimate and assignment.

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
export TRIAL_START_DATE='YYYY-MM-DD' # confirmed trial credit start date
export TRIAL_END_DATE='YYYY-MM-DD'   # confirmed 90-day trial end date
```

## Phase 1 — preparation and cost safeguards

### Read-only preflight

These commands inspect local identity and the selected project; they create no
cloud resources.

```sh
gcloud auth list --filter='status:ACTIVE' --format='table(account,status)'
gcloud config set project "$PROJECT_ID"
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
Cloud DNS and Cloud Logging stay disabled until separately approved. API
activation changes the project, though these APIs have no direct per-request
price.

```sh
gcloud services enable \
  compute.googleapis.com \
  iam.googleapis.com \
  cloudresourcemanager.googleapis.com \
  serviceusage.googleapis.com \
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
or 2376. Public TCP 80/443 is deferred to Phase 3 until domain, DNS, OAuth,
and secret setup are approved.

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
Reserve a regional static external IPv4 now and attach it to the VM; domain
selection is not needed. Record the address. The assigned address costs the
in-use rate even before DNS points to it. Do not leave it unassigned; unused
static IPs cost more. Keep public web ingress closed until Phase 3.

```sh
gcloud compute disks create sigma-state --project="$PROJECT_ID" \
  --zone="$ZONE" --size=200GB --type=pd-balanced \
  --labels=app=sigma,environment=production
gcloud compute addresses create sigma-web-ip --project="$PROJECT_ID" \
  --region="$REGION" --network-tier=PREMIUM \
  --description='SIGMA production endpoint; domain to be selected'
gcloud compute addresses describe sigma-web-ip --project="$PROJECT_ID" \
  --region="$REGION" --format='value(address)'
```

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

### Private host setup before a domain

1. Through IAP, verify Ubuntu release, disk identity/size, OS Login, shielded
   state, package-update policy, time sync, and absence of public SSH. Format
   and mount the state disk at `/srv/sigma-state` only after verifying it is
   the new `sigma-state` disk.
2. Install Docker Engine/Compose using the reviewed Ubuntu procedure in
   `docs/GCP-DEPLOYMENT.md`. Create the separate `sigma-sandbox` account and
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
after domain selection. VM creation, disk mount, Docker installation, and
image builds are independent of the domain.

### Domain, production OAuth, secrets, public ingress, launch

Each action below needs explicit operator approval:

1. Choose an existing approved domain and DNS host. Point its A record to the
   reserved IP. If Cloud DNS is chosen, approve/enable `dns.googleapis.com`,
   zone costs, registrar nameserver delegation, and exact record. Do not buy a
   domain here.
2. Create a production Google OAuth Web client, separate from localhost
   testing, with origin `https://APPROVED_DOMAIN` and exact callback
   `https://APPROVED_DOMAIN/api/cloud-auth/callback`. Verify consent-screen
   policy and approved admin/test-user list. Secret owner stores OAuth secret
   and separately authorized OpenAI key in the approved Secret Manager
   resources through the secure interface.
3. Set the approved domain, TLS contact, admin/contact, OAuth client ID,
   release SHA, state mount, and actual rootless socket/GID in
   `/etc/sigma/deploy.env`. Keep only file paths for secret settings. Set root
   ownership and mode `0600`.
4. Run `sudo deploy/fetch-secrets.sh "$PROJECT_ID" "$OAUTH_SECRET"
   "$OPENAI_SECRET"`. Check owner/mode/size without displaying payloads. Do
   not start until sponsored inference budgets/access were separately
   approved.
5. Verify DNS A/AAAA propagation. Then create web ingress, add the web tag,
   and start Compose. Caddy obtains HTTPS only after DNS and firewall checks.

```sh
gcloud compute firewall-rules create sigma-allow-web \
  --project="$PROJECT_ID" --network="$VPC_NAME" --direction=INGRESS \
  --priority=1000 --action=ALLOW --rules=tcp:80,tcp:443 \
  --source-ranges=0.0.0.0/0 --target-tags=sigma-web
gcloud compute instances add-tags "$VM_NAME" --project="$PROJECT_ID" \
  --zone="$ZONE" --tags=sigma-web
```

After verifying env and secret files on the VM:

```sh
cd /opt/sigma/current
docker compose --env-file /etc/sigma/deploy.env \
  -f deploy/compose.yaml -f deploy/compose.gce.yaml config --quiet
docker compose --env-file /etc/sigma/deploy.env \
  -f deploy/compose.yaml -f deploy/compose.gce.yaml up --build --detach
```

Keep container ports private. Never enable public TCP/8000, 5173, 2375, or
2376. Use the backup/update/rollback instructions in `docs/GCP-DEPLOYMENT.md`
before any release update.

## Cost estimate and trial limitations

Planning estimate carried from `docs/GCP-DEPLOYMENT.md`, USD list prices as
checked 2026-10-23, 730 hours/month and 2,160 hours/90 days, before tax,
discounts, changing prices, or OpenAI usage:

| Item | Assumption | Monthly | 90 days |
| --- | --- | ---: | ---: |
| `e2-standard-4` | Always on, ~`$0.13402284`/h | $97.84 | $289.49 |
| 100 GiB standard boot disk | `$0.0000548`/GiB-h | $4.00 | $11.84 |
| 200 GiB balanced state disk | `$0.00013699`/GiB-h | $20.00 | $59.18 |
| In-use static external IPv4 | `$0.005`/h | $3.65 | $10.80 |
| Snapshot storage allowance | 100 GiB at `$0.000068493`/GiB-h | $5.00 | $14.79 |
| Cloud Storage backup copy | 50 GiB Standard at `$0.02`/GiB-month | $1.00 | $3.00 |
| North America egress | 10 GiB/mo, first 1 GiB free, then `$0.12`/GiB | $1.08 | $3.24 |
| Cloud DNS | One zone + 500k queries | $0.40 | $1.20 |
| Secret Manager / Cloud Logging | Low-volume secret use / logging disabled | $0.00 | $0.00 |
| **Total including later DNS/backups** | Domain registration excluded | **$132.97** | **$393.54** |

This scenario consumes the $300 trial credit around day 69 and exceeds it by
about $93.54 over 90 days. DNS, backups, snapshots, egress, tax, regional
pricing changes, and domain fees vary. A VM created before domain selection
but left running costs roughly the same compute, disk, and attached-IP rates;
DNS is deferred. An unused, unattached static address costs more than the
in-use address. A stopped VM still incurs disk charges. See the [Pricing
Calculator](https://cloud.google.com/products/calculator) and current [Compute](https://cloud.google.com/products/compute/pricing/general-purpose),
[disk/snapshot](https://cloud.google.com/compute/disks-image-pricing),
[network/IP](https://cloud.google.com/vpc/pricing), [Cloud DNS](https://cloud.google.com/dns/pricing),
and [Secret Manager](https://cloud.google.com/secret-manager/pricing) rates
before approval. This is a planning estimate, not a quote.

Trial use requires explicit account-owner approval. Trial credit does not
cover OpenAI API usage or domain purchase. Do not upgrade or add paid billing
to avoid shutdown without explicit budget authorization. Budget alerts do not
cap spend. Trial closure stops associated resources, so the state disk is not
an independent backup; retain an approved backup and decide on recovery,
shutdown, or paid continuation before the trial ends.

## Post-provision validation checklist

- [ ] VM is in approved project/zone with the approved machine, Ubuntu amd64,
  shielded settings, deletion protection, and resource labels.
- [ ] Static IPv4 is attached and recorded; no DNS change occurred before
  domain approval.
- [ ] State disk is the approved 200 GiB balanced volume, attached with
  auto-delete disabled, mounted at `/srv/sigma-state`, and survives VM restart.
- [ ] IAP SSH works only for named maintainers; no public `:22`; OS Login is
  enabled; runtime service account has no key and only two secret-level grants.
- [ ] Before domain approval only IAP TCP/22 is allowed; public 80/443 remain
  closed. No app or Docker ports are public.
- [ ] Budget and recipients are verified in Billing; operator understands it
  is an alert rather than a hard limit.
- [ ] Docker/Compose, mount-before-start ordering, and rootless sandbox daemon
  are installed. Backend can access only the rootless socket; runner and other
  OS users cannot access app state or rootful Docker.
- [ ] Locked backend/frontend/Python/Sage images build locally. Bounded offline
  runner returns expected output under configured limits. Record build time,
  peak RAM, disk headroom, and image sizes.
- [ ] Before public launch: OAuth origin/callback match domain; secret files
  have correct ownership/mode without displaying values; Caddy has HTTPS;
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
