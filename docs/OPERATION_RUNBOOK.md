# SIGMA Operations Runbook

**Status:** Operator procedures for the GCE deployment at `sigma-research.duckdns.org`. Keep this document current as deployment is exercised. **Do not treat proposed commands as executed evidence.**

Detailed configuration and provisioning parameters live in [CLOUD_DEPLOYMENT.md](CLOUD_DEPLOYMENT.md). This is the **long-form host inventory, incident-recovery reference, and deployment evidence archive**, not another routine deployment checklist. Use the [routine release runbook](DEPLOYMENT_RUNBOOK.md#routine-keyless-gce-release--canonical-ordered-path-issue-667) only after explicit release authorization. Record actual commands, outcomes, IDs and dates; never publish secrets, access tokens or user data.

For **routine production deployments**, follow the single ordered
[canonical keyless release path](DEPLOYMENT_RUNBOOK.md#routine-keyless-gce-release--canonical-ordered-path-issue-667).
The generic host, restore, and rollback sections below document operational
primitives and incident procedures, not additional routine checklists.

## Deployment inventory and operator evidence (T127)

This runbook and [CLOUD_DEPLOYMENT.md](CLOUD_DEPLOYMENT.md#observed-deployment) are the maintained records. The deployment coordinator records actual IDs, resource creation, verification results, dates, and deviations as the operator supplies evidence. **The operator should not need to maintain a separate checklist or remember identifiers.** Proposed resource names must not be presented as live resources.

| Item | Current record | Verification |
| --- | --- | --- |
| Google OAuth project | `SIGMA Auth`; ID `sigma-auth-512601`; number `665111821572` | Operator read from Cloud Console, 2026-10-25 |
| Infrastructure project | `SIGMA Production`; ID `sigma-research-prod`; number `224387813390` | Operator-reported created in Cloud Console, 2026-10-25; current billing and effective IAM not independently audited |
| DNS hostname | `sigma-research.duckdns.org` (DuckDNS) | A resolves to `136.66.128.82`; public HTTPS/API probe passed 2026-10-26 |
| Zone and VM | `us-west1-b`; `sigma-gce-01`, Ubuntu 24.04 amd64, `e2-standard-2` | RUNNING; IAP/OS Login verified 2026-10-26 |
| Disk | `sigma-state` 30 GB `pd-balanced`, zonal `us-west1-b`; boot disk 100 GiB `pd-standard` | Attached, mounted with approved UUID/options; one-off recovery snapshot READY 2026-10-26 |
| Network | `sigma-vpc`, subnet `sigma-us-west1` in `us-west1`, primary IPv4 `10.42.0.0/24`; static external IPv4 `sigma-web-ip` = **`136.66.128.82`** (Premium, regional) | Attached to VM; public DNS and HTTPS routing verified 2026-10-26 |
| VM identity and access | `sigma-runtime` service account; IAP SSH with OS Login | VM identity and IAP access verified 2026-10-26; worker IAM remains broader than least privilege |
| Billing account / current spend | Billing was reported enabled and the $300 budget configured in October 2026; regional quota had capacity at the v0.2.2 release | Cloud Billing API is disabled for project `224387813390`, so release identities cannot query current billed spend. The v0.2.2 recovery footprint was bounded and estimated below $25; exact billed amount was not independently queried. |
| Recovery | `sigma-state-v021-pre-20261108-1546` READY from `sigma-state`, snapshot ID `6224195028464248741` | Created 2026-11-08 15:46:18 UTC before v0.2.2 cutover. Isolated read-only restore passed: 3 SQLite integrity checks, 3 identity/workspace mappings, 17 projects, 42 artifacts, one verified TeX/PDF pair, 10 terminal job rows, and 46 accounting call rows ($5.938237 recorded/reserved; 15 reserved or unknown outcomes). Recovery VM, boot disk, clone disk, and ephemeral keys removed and verified absent. Snapshot retained. Daily backup timer and `/etc/sigma/backup.env` remain absent. |
| Production release | `469c955dfadb5a7bd17b72fc069a3365b4f20ba7` (v0.2.2, merged exact SHA) | Deployed 2026-11-08 UTC using the guarded helper. Backend/frontend immutable image IDs and source labels match; all three containers healthy; systemd active; persistent disk mounted; maintenance off. Public HTTPS, hosted auth readiness, anonymous API behavior, and served About bundle provenance passed. Full authenticated account-dependent workflows remain incomplete; see v0.2.2 outcome below. |
| Maintenance page | PR #385 merged at `31ba6c4aba1ed59d2d7e092f589b882d7f134b30` | Installed under `/var/www/sigma-maintenance`; host Caddy 2.6.2 uses the compatible `handle_errors` form; root-owned snippet directory and switch `/usr/local/libexec/sigma/maintenance-switch.py` are installed. Config validation/reload passed. During v0.1.7 cutover the page returned HTTP 503/no-store and the PNG HTTP 200/image/png; maintenance is now off. |

**Change log**

- 2026-11-08: Deployed v0.2.2 from merged exact SHA `469c955dfadb5a7bd17b72fc069a3365b4f20ba7`. Snapshot `sigma-state-v021-pre-20261108-1546` (ID `6224195028464248741`) reached READY and passed the isolated read-only verifier; temporary recovery resources and ephemeral keys were removed. Guarded build/cutover completed at 16:03:35 UTC with a 30-second public maintenance window. All post-deployment health, storage, image provenance, data/accounting, HTTPS, hosted auth readiness, and maintenance-off checks passed. See the detailed v0.2.2 outcome below.

- 2026-11-06: Deployed v0.2.1 from exact approved SHA `5435e14eeea159ab207ad50016577b9a9542ae59` per issue #588. Fresh snapshot `sigma-state-v021-pre-20261107-0658` and isolated read-only restore verification passed; temporary recovery VM/clone disk removed. Guarded build/cutover completed at 07:09 UTC; production smoke and Chrome About verified 0.2.1/build `5435e14`. No paid inference. See detailed outcome below.

- 2026-11-04: Deployed v0.2.0 from exact merged `main` SHA `9d938907ffd02fb89c9d10545e8df61484310cbd`; exact-SHA SIGMA tests, browser acceptance, and Ruff checks passed. Created and read-only restore-verified `sigma-state-v020-pre-20261104-1736`, then deployed using the documented guarded helper. Service stopped at 06:07:16 UTC and became active at 06:07:32 UTC on November 5; public HTTPS returned HTTP 200 afterward. Image IDs, release pin, checkout, state mount, health, and maintenance-off state were verified. Chrome About reported `Version 0.2.0 · Build 9d93890`. Full account-dependent smoke checks are incomplete; see the detailed outcome below.

- 2026-10-30: Deployed v0.1.7 from exact merged `main` SHA `802e9b6b7da5829868070f760e17280cd8a927f2`; PR #389 domain authorization and PR #385 maintenance page are included. PR #390 exact-head checks and merged-main CI passed. Host Caddy setup validated and reloaded without enabling maintenance; guarded deployment observed a ~41-second public 503 maintenance window, followed by HTTP 200. All container/image SHA, state mount, systemd, public API/auth, and headless Chrome checks passed. Issue #383 closed after verification. The operations runbook and related release PRs contain the deployment evidence. The issue had auto-closed at PR merge and was reopened/closed after production verification.

- 2026-10-30: Under operator authorization, fixed production About build provenance. PR #344 passes the exact release SHA to the frontend Docker build; PR #345 ensures the guarded host helper uses candidate deployment tooling before image build. Both PRs passed exact-head CI. Deployed merged SHA `83c89f20e19ea87c4a3b4934942d0a78c2019973`; checkout/pin, image labels, running containers, systemd, state mount, public root, and frontend bundle were verified. The bundle contains `83c89f2`. No data or schema changes, snapshot creation, paid provider calls, or local SIGMA server requests occurred. The existing pre-v0.1.5 READY snapshot remains retained.

- 2026-10-27: Issue #265 diagnosis found production still on initial release `e1ef8db8ea6c15bcb79ad9c8d06e8e5f6f4527f3`; host Caddy correctly routes to the old Compose frontend. Under owner authorization, stopped `sigma.service`, confirmed Compose containers stopped, created READY snapshot `sigma-state-issue265-20261027-075405`, then restarted the service and verified public HTTPS. A no-public-IP, no-service-account recovery VM mounted a snapshot clone read-only with UUID `28ef67cb-4da8-46e7-9a8b-dce0470153a5`. After correcting the restore verifier's database paths to `/auth/workspaces`, the read-only check passed three SQLite databases, two identities/mappings, three projects, ten research artifacts, and accounting references including one reserved/unknown call; no paper pairs existed. The temporary VM and clone disk were removed; the snapshot remains. This verifies a readable recovery point, not a production restore cutover. Merged release `3f2426c6fa83866c655cb1b601a7e2df78e5e459` images built with matching source labels, but production cutover is pending SMTP configuration and final acceptance. Temporary GCE disk/VM and snapshot incurred provider storage/compute charges; exact billed amount is not yet available.

- 2026-10-26: Initial preview deployed from exact SHA `e1ef8db8ea6c15bcb79ad9c8d06e8e5f6f4527f3`. T128 host readiness and all 23 production preflight checks passed; systemd service and three containers are healthy. Removed the retired bootstrap-admin setting while preserving the prior administrator/contact identity and backing up `/etc/sigma/deploy.env`. Created READY recovery snapshot `sigma-state-preview-20261026-063909`. Installed the documented host-Caddy reverse proxy after public probing showed the static readiness page was still active. DNS, HTTPS/TLS, private-port closure, SPA deep link, hosted API readiness, and local headless Chrome smoke passed. No paid inference or IAM/network changes. Formal OAuth, two-identity, research-runtime, reboot-recovery, and restore acceptance remain pending; recurring backup scheduler is not configured.

- 2026-10-25: Operator screenshot showed active Direct billing account `My Billing Account` (`015C1D-E6B877-9913D6`) and $0 spend over 30 days. Project linkage and free trial remain unverified.

- 2026-10-25: Operator created `SIGMA Production`, ID `sigma-research-prod`, project number `224387813390`. Billing and permissions have not yet been verified.

- 2026-10-25: Operator reported existing `SIGMA Auth` project identity (name, project ID, project number). Confirmed selected DuckDNS hostname from approved deployment documentation. No production resources, IAM grants, billing changes, or DNS updates executed by this documentation change.

### T127 Console provisioning log (2026-10-25)

- **Production project:** `SIGMA Production`, ID `sigma-research-prod`, number `224387813390`. Existing auth project: `SIGMA Auth`, ID `sigma-auth-512601`, number `665111821572`.
- **Duplicate project:** `sigma-production-512718` shut down per operator report; in deletion recovery period. Do not confuse with production.
- **Billing:** Active Direct account `My Billing Account`, ID `015C1D-E6B877-9913D6`; production and auth projects linked per Console screenshot. Free trial showed $300 credit and $0 used on October 25. Calculated 90-day end January 22, 2027; confirm Console expiry.
- **Budget:** `SIGMA Production - Trial Budget`, $300, custom October 24, 2026–January 22, 2027. Operator confirmed saved row; alerts at 50%, 75%, 90%, 100%; normal email notifications. Budget alerts do not cap spend.
- **APIs enabled:** Compute Engine, IAM, Cloud Resource Manager, Secret Manager, IAP, Cloud Billing Budgets (operator screenshots/reports).
- **Service account:** `sigma-runtime@sigma-research-prod.iam.gserviceaccount.com` created and enabled, screenshot; project roles left blank, no account keys created. Two secret-level access grants pending.
- **Secret Manager:** Creating first OAuth secret deferred because Console form requires a version value. Neither secret reported created.
- **Hostname:** `sigma-research.duckdns.org`, registered. Static IP and live DNS update pending.
- **Not yet provisioned:** custom VPC/subnet, IAP SSH firewall, state disk, static IP, VM; live SSH and disk checks outstanding.

**T127 cost adjustment (2026-10-25):** State disk initial 200 GiB rejected for cost; 30 GiB subsequently recommended before creation (approximately $17/month less than 200 GiB), pending confirmation. The existing provisioning examples mentioning 200 GiB are superseded for this resource and require reconciliation before use.

- 2026-10-25: Operator completed creation of `sigma-state` as 30 GB zonal balanced disk in `us-west1-b`, selected No backups, Google-managed encryption and no consistency group. Disk-table verification and non-auto-delete attachment pending.

- 2026-10-25: Operator verified reserved regional Premium external IPv4 `sigma-web-ip` = `136.66.128.82`; not yet assigned to VM. DuckDNS A-record update pending.

- 2026-10-25: Human operator confirmed existing project IAM role **Owner** in `sigma-research-prod`. OS Admin Login, IAP tunnel access, and service-account-user grants are not yet verified; do not assume Owner covers those permissions.

**IAM verification (2026-10-25):** Operator screenshot shows named human account assigned Owner, Compute OS Admin Login, and IAP-secured Tunnel User in `sigma-research-prod`. Default Compute Engine service account retains Editor; do not attach it to SIGMA VM. Dedicated runtime service account attachment and its `iam.serviceAccountUser` grant remain to be verified.

**Service account attachment authorization (2026-10-25):** Operator confirmed `roles/iam.serviceAccountUser` saved for the named human operator on the `sigma-runtime` service account resource only. No condition or additional roles; ready for VM attachment.

**VM creation checkpoint (2026-10-25):** Operator confirmed pre-create configuration for `sigma-gce-01`: `e2-standard-2` (2 vCPU, 8 GiB), Ubuntu 24.04 LTS amd64, 100 GB standard boot disk, existing 30 GB `sigma-state` with Keep disk, `sigma-vpc`/`sigma-us-west1`, static IPv4 `136.66.128.82`, IAP-only network tag, `sigma-runtime` with cloud-platform scope, OS Login, shielded settings, deletion protection and labels. VM creation authorized in operator workflow; **creation and running state not yet verified**. This machine type deviates from earlier `e2-standard-4` plan for cost control.

**Live VM status (2026-10-25):** Operator reports `sigma-gce-01` appears with green running status in VM instances and external IPv4 `136.66.128.82`. Attached disk identity/deletion rule, VM detailed settings, and IAP SSH remain to be verified.

**Disk attachment verification (2026-10-25):** Operator confirmed `sigma-state` attached to running `sigma-gce-01`, 30 GB, read/write, deletion rule **Keep disk**. Guest filesystem identity, mount, restart persistence, and IAP SSH are not yet verified.

**IAP SSH verification (2026-10-25):** Operator ran `gcloud compute ssh sigma-gce-01 --project=sigma-research-prod --zone=us-west1-b --tunnel-through-iap` from Google Cloud Shell and successfully reached guest shell without errors. Cloud Shell generated SSH key for OS Login. Read-only guest block-device identity and filesystem checks remain pending.

**Guest device check (2026-10-25):** Read-only `lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS` on `sigma-gce-01` showed `/dev/sda` 100G boot with ext4 root `/`, plus separate `/dev/sdb` 30G with no FSTYPE or mount. Guest by-id mapping and `blkid` still pending before any filesystem initialization.


**State disk filesystem verification (2026-10-25):** Operator verified `google-sigma-state` was blank, created ext4 with label `sigma-state`, and confirmed `blkid` reported UUID `28ef67cb-4da8-46e7-9a8b-dce0470153a5`, type ext4, block size 4096. Initial mount and reboot validation pending. Do not reformat this disk.

**State mount observation (2026-10-25):** Operator mounted UUID `28ef67cb-4da8-46e7-9a8b-dce0470153a5` at `/srv/sigma-state`; `findmnt` showed `/dev/sdb`, ext4, `rw,relatime`. Filesystem root ownership/mode, persistent fstab entry and reboot validation remain pending.

**State mount permissions (2026-10-25):** Operator confirmed `sudo stat -c '%U:%G %a %n' /srv/sigma-state` returned `root:root 700 /srv/sigma-state`. Persistent fstab configuration and reboot validation remain pending.

**T127 reboot acceptance (2026-10-25):** VM boot time `2026-10-25 22:01:51 UTC` after operator reboot. `findmnt /srv/sigma-state` reported `/dev/sdb` ext4 `rw,relatime`; `stat` reported `root:root 700`. Persistent UUID mount survived reboot. Host application installation, backup policy, and hosted launch remain separate work.

## Before any operation

1. Identify the GCP project, `us-west1-b` zone, VM `sigma-gce-01`, disk `sigma-state`, public hostname, and current `SIGMA_RELEASE`. Confirm these against **live GCP**, not just this document.
2. Identify impact: read-only, write, downtime, user data, security, external resources or provider calls. Obtain owner authorization for material changes. Warn users before downtime.
3. Confirm healthy **recent recoverable backup** before deployment, migration or restoration. Never operate on an unverified disk, or run `gcloud` commands with unresolved placeholders.
4. Verify `/srv/sigma-state` is the **attached persistent disk**, mounted with expected filesystem UUID and restrictive permissions. **Never fall back to boot/container storage**.
5. Prefer `sudo systemctl ... sigma.service` for the production application. Do **not** run production Compose `up` manually, mount a rootful Docker socket, or use `--allow-nonrootless-dev` for acceptance.

## 1. Provision a new host (once per VM)

**Replacement-host procedure only.** SIGMA is already deployed on
`sigma-gce-01`; do not rerun these provisioning steps on that VM. For current
production operations, use the diagnosis, release, backup, and rollback
sections below. This procedure does not update application code on the existing
host.

**Prerequisites:** Explicit approved GCP project/resources, IAM, static IP, state disk, Secret Manager configuration, production Google OAuth Web client and DuckDNS access.

1. Review [T128 host readiness](T128_HOST_READINESS.md) and the historical
   [hosting decisions](CLOUD_DEPLOYMENT.md#historical-hosting-and-external-host-notes).
   Obtain separate approval for each new resource, size, billing exposure, and
   network rule. Provision Ubuntu 24.04 amd64 in `us-west1-b` with a separately
   retained state disk (`auto-delete=no`). Restrict SSH to the approved IAP
   path, and enable public ingress only when the launch gates are satisfied.
2. Confirm the attached `sigma-state` disk identity before initial filesystem
   setup. **Never format an existing disk**. If the owner-confirmed new disk is
   blank, perform any required one-time formatting only after verifying its
   GCE attachment. Once its filesystem UUID is known, run:

   ```sh
   sudo /opt/sigma/current/deploy/prepare_state_disk.py OWNER_CONFIRMED_UUID
   ```

   This writes an idempotent UUID-backed `/etc/fstab` entry with restrictive
   mount flags, mounts at `/srv/sigma-state`, and makes the filesystem root
   `root:root 0700`. It does not format disks. The preflight confirms that the
   mounted UUID and fstab UUID match; `sigma.service` requires the generated
   mount unit and fails closed when the disk is absent.
3. Stage reviewed code at `/opt/sigma/current` and run `sudo /opt/sigma/current/deploy/install-gce-host.sh`. Install/configure the dedicated `sigma-sandbox` rootless Docker daemon.
4. Build Python and Sage runner images **under the rootless daemon** using `deploy/build-sandbox-images.sh`, as described in the Cloud Deployment host setup contract.
5. Set `/etc/sigma/deploy.env` with release SHA, domain, OAuth client ID, approved limits and secret-file paths; protect it `root:root 0600`. Use `deploy/fetch-secrets.sh` for named secrets. Never print secret values.
6. Run `sudo /usr/local/libexec/sigma/gce_preflight.py --json --repository /opt/sigma/current`; proceed only on PASS/exit 0. The installed script is outside the checkout, so pass the repository path explicitly for Compose checks. Run `python -m sigma.cloud_runtime_check` against the **actual rootless** daemon only as a separately approved sandbox exercise; it starts a runtime probe and writes temporary evidence.
7. Configure DuckDNS A record to the reserved static IP; verify external DNS and HTTPS/Caddy certificate. Set Google OAuth allowed origin `https://sigma-research.duckdns.org` and callback `https://sigma-research.duckdns.org/api/cloud-auth/callback`.
8. Start with `sudo systemctl enable --now sigma.service`. Check Caddy/API/frontend health, auth mode, private state mounts, logs and research sandbox isolation. Record actual endpoint results.
9. Complete hosted acceptance before inviting users: two distinct Google identities, unauthorized access rejection, workspace isolation, bounded sponsored inference, Python/Sage, sessions/recovery, Markdown/TeX/PDF/report export, browser restart and data persistence. **Desktop browser is the release target; mobile-specific acceptance is out of scope.**

For T134's repeatable two-identity privacy matrix, direct-reference probes,
sign-out/sign-in transitions, no-mutation checks and sanitized evidence template,
see [T134 hosted acceptance](T134_HOSTED_ACCEPTANCE.md). Do not run provider-backed
checks without separate authorization. Local fixtures do not satisfy hosted acceptance.
For deterministic hosted research API coverage, target-rootless Python/Sage
proof, provider authorization boundaries, and the T132 evidence record, see
[T132 hosted research acceptance](T132_HOSTED_RESEARCH_ACCEPTANCE.md).
For production Google OAuth settings and the focused desktop sign-in, callback,
session, sign-out, denial and account-switch procedure, see
[T131 hosted OAuth acceptance](T131_HOSTED_OAUTH_ACCEPTANCE.md). Hosted OAuth
acceptance requires saved settings, a deployed SHA, HTTPS and owner-authorized
test identities; local tests remain preparation evidence only.

## 2. Routine health and diagnosis

Use read-only commands on host:

```sh
sudo systemctl status sigma.service --no-pager
sudo systemctl status 'srv-sigma\x2dstate.mount' --no-pager
findmnt /srv/sigma-state
sudo /usr/local/libexec/sigma/gce_preflight.py --json \
  --repository /opt/sigma/current --env-file /etc/sigma/deploy.env
sudo journalctl -u sigma.service -n 100 --no-pager
```

Verify public DNS, HTTPS, `/api` routing and application health with the read-only probe below, not only process status. Run it from a network outside the VM so public firewall behavior is observed. It compares the DNS A answer with the owner-verified static IPv4, checks that TCP 8000/5173/2375/2376 are unreachable, requires HTTP `/` to redirect to the canonical HTTPS origin, validates the certificate with the system trust store, checks an SPA deep link, and requires hosted API readiness. It changes no DNS, cloud firewall, or application state. Redact tokens, personal data and request bodies from captured logs. For failure classify DNS/TLS, VM/network, disk mount, Docker/rootless socket, service, OAuth, secret access, quota, provider or persistent state before restarting.

```sh
cd /opt/sigma/current
python3 deploy/verify_public_endpoint.py --expected-ip OWNER_VERIFIED_STATIC_IPV4
```

When running the probe from a source checkout that is not installed as a
package, set `PYTHONPATH=src` (or run it through the project environment), for
example `PYTHONPATH=src python3 deploy/verify_public_endpoint.py
--expected-ip 136.66.128.82`.

The GCP ingress contract allows only public TCP 80/443 after launch approval;
TCP 22 remains IAP-only. Do not add public TCP 8000, 5173, 2375 or 2376.
Host Caddy owns public HTTPS and redirects HTTP to HTTPS. The GCE Compose edge
publishes only `127.0.0.1:18080` and serves HTTP behind host Caddy. Configure
the existing host Caddy with the site block in `deploy/host-caddy.Caddyfile`;
it forwards requests to that loopback listener. The Compose Caddy routes `/api`
and `/api/*` to FastAPI and other paths to the SPA frontend. A successful
DNS/TLS probe is endpoint evidence, not proof of OAuth identity isolation or
persistent-state recovery.

After starting or restarting the service, verify all three container healthchecks
and the public app/API paths. Run on the host from the reviewed release
checkout; this uses the system Docker daemon for Compose and does not start or
mutate the stack:

```sh
cd /opt/sigma/current
compose=(sudo docker compose --project-name sigma --env-file /etc/sigma/deploy.env \
  -f deploy/compose.yaml -f deploy/compose.gce.yaml)
for service in backend frontend edge; do
  container=$("${compose[@]}" ps -q "$service")
  test -n "$container"
  test "$(sudo docker inspect --format '{{.State.Health.Status}}' "$container")" = healthy
done
curl --fail --silent --show-error https://sigma-research.duckdns.org/ -o /dev/null
curl --fail --silent --show-error https://sigma-research.duckdns.org/api/cloud-auth/status \
  | python3 -c 'import json,sys; s=json.load(sys.stdin); assert s["enabled"] and s["ready"] and s["target"] == "hosted"'
findmnt --mountpoint /srv/sigma-state --output SOURCE,UUID,FSTYPE,OPTIONS
sudo stat -c '%U:%G %a %n' /srv/sigma-state /srv/sigma-state/auth
sudo docker inspect --format '{{.Mounts}}' "$("${compose[@]}" ps -q backend)"
```

The backend healthcheck validates hosted auth, persistent storage, required
secret configuration, spending limits and rootless Docker reachability. The
frontend probes its Nginx listener; Caddy probes its loopback-only admin API.
The edge waits for both application healthchecks before starting. Require the
state mount UUID to match the approved disk inventory and `/srv/sigma-state`
to remain `root:root` mode `700`; `auth` must be the mounted disk's
`10001:10001` mode `700` directory. The Compose bind source must resolve to
`/srv/sigma-state/auth`. Container health alone does not prove hosted identity,
workspace privacy or saved-state recovery; those checks remain separate.

### Automated host and backup checks (T136)

After T128/T129 host setup and the T135 scheduler are installed, configure the
owner-approved `/etc/sigma/backup.env` and install Gray's independent,
read-only monitor:

```sh
sudo /opt/sigma/current/deploy/install-host-monitor.sh
sudo systemctl start sigma-monitor.service
sudo systemctl status sigma-monitor.timer --no-pager
sudo journalctl -u sigma-monitor.service -n 100 --no-pager
```

The timer runs at boot and every 15 minutes. It checks the state mount, free
filesystem capacity (minimum 15%) and inodes (minimum 5%), Docker/systemd
dependencies, backend/frontend healthchecks and edge container state, backup
failure and freshness markers (successful point within 26 hours), and at least
14 managed `READY` recovery points. Any failure returns nonzero and includes a
specific next action. Output excludes raw command output, request bodies,
workspace names, credentials and user data. The failure unit records a critical
system journal entry; this is **local detection, not a remote pager**. Until an
owner approves an external alert path, an operator reviews results at least
daily. The monitor uses the existing approved backup project setting and does
not create or delete GCP resources.
The installer leaves the timer enabled if its initial check fails (for example,
before 14 recovery points exist); treat this as unresolved host failure, not
installation acceptance.

```sh
sudo systemctl show sigma-monitor.service -p Result -p ExecMainStatus
sudo journalctl -u sigma-monitor.service -u sigma-monitor-failure.service --since today --no-pager
sudo df -h /srv/sigma-state
sudo df -i /srv/sigma-state
sudo systemctl status sigma-backup.timer sigma-backup.service --no-pager
sudo cat /var/lib/sigma-backup/last-success
sudo test ! -e /var/lib/sigma-backup/last-failure
```

Do not clear failure markers or lower thresholds to obtain a green result. For
capacity failures, stop admitting new research and arrange approved disk
expansion; do not remove workspaces, SQLite databases, artifacts, snapshots or
Docker volumes. For backup failures, inspect service journals, mount identity,
IAM and `READY` point inventory. Restore a current successful point, then
restore the 14-point retention invariant.

## 3. Restart service / recover after VM reboot

1. Check state disk mount and preflight first; **do not start** if storage is absent or permissions differ.
2. `sudo systemctl restart sigma.service`; check `systemctl status`, logs, HTTPS and app health.
3. Verify existing saved project, sessions, paper artifacts, Google subject mapping and usage ledger remain intact.
4. Treat interrupted provider calls as **uncertain** and retain pending reservations. Never replay billable requests or edit the usage ledger to make the UI look healthy.
5. For VM reboot, check ordering and recovery before reopening traffic:

   ```sh
   sudo systemctl status 'srv-sigma\x2dstate.mount' docker.service sigma-sandbox.service sigma.service --no-pager
   findmnt /srv/sigma-state
   sudo /usr/local/libexec/sigma/gce_preflight.py --json \
     --repository /opt/sigma/current
   sudo systemctl status sigma-backup.timer sigma-monitor.timer --no-pager
   sudo systemctl start sigma-monitor.service
   sudo journalctl -b -u 'srv-sigma\x2dstate.mount' -u sigma-sandbox.service -u sigma.service --no-pager
   ```

   Require the expected persistent disk/UUID, preflight exit 0, active Docker
   and rootless sandbox services, active `sigma.service`, healthy backend and
   frontend, running edge and passing monitor. Verify public HTTPS/API, known
   authorized test identities, workspace boundaries, saved project/research
   artifacts, usage totals and pending/unknown reservations against pre-reboot
   evidence. Never release/replay an interrupted reservation to make totals
   look clean; provider outcome may be uncertain. Record deployed SHA and boot
   ID. Local unit/container checks are not hosted acceptance.

## 4. Application release / update

**For routine deployments, use the canonical guarded-release sequence in
[DEPLOYMENT_RUNBOOK.md](DEPLOYMENT_RUNBOOK.md#routine-keyless-gce-release--canonical-ordered-path-issue-667).**
The following manual steps are historical/incident reference, not a shortcut
around the exact-SHA recovery and helper gates.

1. Confirm candidate full Git SHA, reviewed PR, verified tests/browser evidence, and known migrations. Ensure backup/restore point is current.
2. From a repository checkout with the candidate commit available, build release images using `python3 /path/to/checkout/deploy/release_image.py build /path/to/checkout FULL_40_CHAR_SHA`. This exports the requested commit from Git, so dirty files and the checkout's current HEAD are not build inputs. The command fails if the exact commit cannot be resolved. Inspect the generated `sigma-backend:SHA` and `sigma-frontend:SHA` image labels before proceeding. If the sandbox image source changed, rebuild the rootless Python/Sage images.
3. Before a disruptive release, use the host-Caddy maintenance switch in
   [the maintenance setup](../deploy/maintenance/README.md). Verify the branded
   page is served with HTTP 503 and its image with HTTP 200. The guarded release
   helper enables maintenance before stopping SIGMA and disables it only after
   replacement health checks pass. For a manual cutover, keep it enabled until
   the candidate or restored previous release passes health checks; then disable
   it and verify the normal app is public again. Stop production through
   `sudo systemctl stop sigma.service` only for the documented snapshot or
   deployment sequence.
4. Update `SIGMA_RELEASE` in protected `/etc/sigma/deploy.env` to that same full SHA. Do not change state volume mapping or delete Compose volumes.
5. Run preflight; start via `sudo systemctl start sigma.service`. Startup verifies both image source labels and uses Compose `--no-build`; it records the source commit, actual running container IDs, immutable image IDs and any repository digests in `/var/lib/sigma/releases/SHA.json`. Verify that record and the running containers, then verify auth, existing users, project/session persistence, bounded research, exports and HTTPS.
6. If verification fails, use rollback below. Record SHA, downtime, tests and outcome.

## 5. Daily state-disk backup

### Fresh pre-release recovery point and restore verification (v0.1.5 readiness)

The existing `sigma-state-v014-20261029-0606` is READY but has not been
restore-tested; it is not evidence of current v0.1.4 data recoverability. The
daily backup timer and `/etc/sigma/backup.env` were absent at inspection. After
the operator authorized the v0.1.5 deployment process, a fresh
application-consistent snapshot `sigma-state-v015-pre-20261030-0506` reached
READY at 2026-10-29 22:06:32 PDT from `sigma-state`. The service was stopped,
Compose writers were confirmed stopped, and the mounted state disk was synced
before snapshot creation. SIGMA was restarted and the service plus backend,
frontend, and edge containers were confirmed healthy/running. The isolated
restore check passed on a clone attached READ_ONLY to a temporary recovery VM
with no public IP or service account, mounted `ro,nosuid,nodev,noexec,norecovery`.
The verifier passed SQLite integrity, three identities/mappings, 12 projects,
30 research artifacts, paper-file checks (zero saved PDF/TeX pairs), and all
accounting checks. It retained ten terminal historical job rows across two
removed workspaces; no active jobs or spending-call rows referenced them. The
projects were schemas 8 (11 records) and 9 (one record); none were missing or
invalid. The verifier correction is in PR #343 and remains subject to exact-head
CI/merge. Temporary VM and clone disk are pending cleanup; retain the snapshot.

For the v0.1.5 drill, the operator account had project Owner and billing was
enabled; the required zone quotas had capacity. No IAM grant was made to the
runtime service account. The one-time snapshot used operator GCP credentials
after stopping and syncing the source; the recurring timer remains disabled.
No numeric cost ceiling or current billed amount was obtained. Temporary
snapshot/clone/compute charges are possible, so remove only the recovery VM and
clone disk after preserving verification evidence. Keep the recovery snapshot.

For future recurring backups, review and record before enabling the timer:

1. Audit current project billing, quota, effective operator IAM, VM service
   account grants and metadata credential isolation. The backup script needs
   Compute permissions to get the source disk, create a snapshot, inspect/list
   snapshots, and delete only managed expired snapshots. Grant only the
   approved least-privilege role to the operator executing the drill; do not
   broaden the runtime service account as a shortcut. The restore clone needs
   disk create/attach permissions and an isolated recovery host needs only the
   access needed for the offline verifier. The v0.1.5 one-time drill used the
   operator identity; the VM service account still lacks project-level snapshot
   bindings. Do not grant it extra IAM just to avoid an operator-mediated run.
2. Agree on a cost ceiling and confirm current billing/quota. Costs may include
   changed-block snapshot storage, a clone disk, temporary recovery compute,
   and access logging. Current spend and rates were not verified; no amount is
   asserted here. A budget alert is not a spending cap.
3. Schedule a maintenance window. The backup script stops `sigma.service`,
   confirms Compose writers stopped, syncs the mounted source disk, waits for a
   READY snapshot before pruning, records the result, and restarts the service
   on exit. Production downtime lasts through snapshot completion and restart;
   the duration is unknown until measured. Confirm no other writer is active,
   and monitor the systemd journal and external health after restart.
4. After explicit approval, invoke the already-installed script with
   one-shot parameters (this does not install persistent backup configuration):

   ```sh
   sudo env SIGMA_BACKUP_PROJECT=sigma-research-prod \
     SIGMA_BACKUP_ZONE=us-west1-b SIGMA_BACKUP_DISK=sigma-state \
     SIGMA_BACKUP_RETENTION=14 /opt/sigma/current/deploy/backup-state.sh
   ```

   Require exit 0, a named READY snapshot with source `sigma-state`, and a
   healthy restarted service. Do not prune manually or continue after a failed
   snapshot or restart.
5. Create a named clone from that exact snapshot and attach it only to a
   temporary recovery host with no public IP, no production service account,
   no OAuth/provider credentials and no ingress. Mount the clone read-only
   with `ro,noload,nosuid,nodev,noexec`; verify the device, filesystem UUID,
   and mount options before running the packaged `verify-state-restore.py`.
   Set minimum expected identity/workspace/project/artifact/paper and
   accounting thresholds from an operator-approved aggregate baseline. Require
   every verifier check to pass, preserve sanitized evidence and the snapshot,
   then remove only the temporary recovery VM and clone disk created by the
   drill. Retain the recovery snapshot. Never mount the clone writable or
   attach it to the production VM. The verifier is read-only and offline; it
   does not prove browser/API behavior or a production restore.

Restore requires operator review because clone disk/VM and snapshot storage
incur charges and the source snapshot requires downtime. For the authorized
v0.1.5 drill, billing was enabled and quotas had capacity, but a dollar cost
ceiling and current billed amount were not established. The one-time snapshot
and read-only restore check have passed; temporary VM/disk cleanup remains.
Review IAM, billing, quotas, maintenance window and expected data thresholds
before enabling recurring backup configuration.

For an explicitly assigned routine production release, Red is the recovery
owner and may create the isolated recovery VM and clone disk without another
human approval. Use an existing READY snapshot where possible, verify live
billing, least-privilege access and quota first, and cap incremental temporary
resource cost at $25. Record the actual maintenance window and verifier
thresholds before the drill. Remove only the temporary VM and clone disk after
preserving evidence; retain the recovery snapshot. If a gate fails or expected
cost exceeds $25, leave production untouched and report the blocker. This
routine-release scope does not authorize recurring backup changes, IAM
broadening, production data restoration, or paid inference.

The installed `sigma-backup.timer` runs at 10:17 UTC daily with `Persistent=true`
(about 02:17 or 03:17 in Oregon, depending on daylight saving time).
`sigma-backup.service` stops `sigma.service`, verifies that no SIGMA Compose
container remains running, snapshots the attached `sigma-state` disk, waits for
the snapshot to report `READY`, and only then prunes managed snapshots beyond
the configured retention (minimum 14). It restarts the app if it was active
before the run. A failed job is visible as a failed systemd unit, a critical
journal entry, and `/var/lib/sigma-backup/last-failure`; inspect all three.

Before enabling the timer, obtain owner approval for snapshot IAM, cost and
retention. The VM identity needs only the snapshot and disk inspection actions
needed by the script; verify that app containers cannot use those credentials
through the GCE metadata server. If that isolation cannot be demonstrated,
do not enable the timer. Each run takes the hosted app offline while SIGMA is
stopped; announce the daily maintenance window before enabling the timer. The
backup service uses the host's GCE credentials;
it does not put a key in the repository or state disk.

1. Confirm the live project, zone, attached source disk, `/srv/sigma-state`
   mount, `sigma.service`, and host identity. Do not proceed on an unmounted
   state disk or a boot-disk fallback.
2. Create `/etc/sigma/backup.env` from the reviewed
   [`backup.env.example`](../deploy/backup.env.example). Set the approved
   project ID, zone, disk name and retention (14 or greater); install it
   `root:root` mode `0600`. It contains no credentials.

   ```sh
   sudo install -o root -g root -m 0600 \
     /opt/sigma/current/deploy/backup.env.example /etc/sigma/backup.env
   sudoedit /etc/sigma/backup.env
   sudo stat -c '%U:%G %a %n' /etc/sigma/backup.env
   ```
3. Review `deploy/install-backup-scheduler.sh` and install from the reviewed
   release checkout:

   ```sh
   sudo /opt/sigma/current/deploy/install-backup-scheduler.sh
   sudo systemctl status sigma-backup.timer --no-pager
   sudo systemctl list-timers sigma-backup.timer --no-pager
   ```

4. After owner approval, run the first real backup and wait for completion:

   ```sh
   sudo systemctl start sigma-backup.service
   sudo systemctl status sigma-backup.service --no-pager
   sudo cat /var/lib/sigma-backup/last-success
   sudo gcloud compute snapshots list --project=APPROVED_PROJECT \
     --filter='labels.sigma-daily-backup=true AND status=READY' \
     --format='table(name,creationTimestamp,sourceDisk,labels)'
   ```

   Check that the named recovery point has the expected `sigma-state` source,
   the `sigma-daily-backup=true` and `sigma-source-disk=sigma-state` labels,
   and `READY` status. The systemd success status and a snapshot existing alone
   do not prove that a restore works. Do not manually delete a recovery point
   to fix a failed run.
5. Confirm the service came back if it was active before the backup. Check
   `sudo systemctl status sigma.service`, state mount, public health and a
   saved workspace. Record UTC timestamp, snapshot ID, source disk and release
   SHA using the completion template.
6. Inspect scheduling and failures:

   ```sh
   sudo systemctl list-timers sigma-backup.timer --all --no-pager
   sudo systemctl status sigma-backup.service --no-pager
   sudo journalctl -u sigma-backup.service -u sigma-backup-failure.service -n 100 --no-pager
   sudo cat /var/lib/sigma-backup/last-success
   sudo test ! -e /var/lib/sigma-backup/last-failure
   ```

**Troubleshooting:**

- `sigma-backup.service` is `failed`: read
  `journalctl -u sigma-backup.service -u sigma-backup-failure.service`; check
  `/var/lib/sigma-backup/last-failure`. Resolve the stated cause, verify app
  health and mount, then explicitly rerun `sudo systemctl start
  sigma-backup.service`. A retry is not automatic evidence; record its result.
- Timer has no next run: check
  `systemctl status sigma-backup.timer` and `systemctl list-timers --all`; run
  `sudo systemctl daemon-reload` only after reviewing installed unit contents,
  then `sudo systemctl restart sigma-backup.timer`.
- Backup rejects the mount or still-running containers: do not bypass the
  guard. Confirm the actual `sigma-state` disk is mounted at
  `/srv/sigma-state`, `sigma.service` is stopped, and no SIGMA Compose project
  containers remain. Escalate any independent writer.
- GCE reports permission denied, quota, or snapshot failure: the app is
  restarted by the service exit handler if it was previously active, and no
  managed snapshot is pruned before the new point reaches `READY`. Verify the
  approved project/zone/disk and least-privilege IAM with the owner; do not
  grant project-wide Editor/Owner or put a service-account key on the VM.
- `last-success` is stale or `last-failure` exists: treat the backup as
  overdue/failed until a new run completes and a `READY` snapshot is confirmed.
  `OnFailure` writes a critical local journal record; no external alert channel
  is configured by this change, so the operator must monitor systemd/journal
  status through the approved host monitoring process.
- Service failed to restart after backup: keep the recovery point; inspect
  `sigma.service` logs, mount and preflight. Do not launch production Compose
  manually or run the backup repeatedly against an unhealthy stack.

**Consistency boundary:** the app is unavailable while stopped; the snapshot
includes the whole dedicated disk, keeping auth identities, subject/workspace
mappings, each workspace and its projects/sessions/research artifacts, and the
cloud-research usage ledger at the same quiesced point. No independent writer
may touch these files during the operation. Interrupted provider work may have
an unknown external charge; its reserved/unknown accounting state is preserved
and must not be replayed or cleared.

**Recovery limits:** snapshots are in the same GCP project and use the project's
snapshot access controls. They do not protect against loss, suspension or
compromise of that project or its privileged IAM. This change does not create
an off-project archive. A failed/missed schedule can create a recovery gap;
daily scheduling targets at most roughly 24 hours of data loss but provides no
RPO guarantee. No RTO is claimed. A successful snapshot is not restore evidence.

## 6. Restore drill (non-production) / disaster recovery

A routine release must follow the single [keyless sequence](DEPLOYMENT_RUNBOOK.md#routine-keyless-gce-release--canonical-ordered-path-issue-667):
fresh application-consistent snapshot, deterministic no-address/no-service-account
OS Login recovery VM, read-only disk attachment and mount, strict verifier,
and temporary-resource cleanup. The examples below cover generic/incident
recovery and are not a second routine-release checklist.

1. Choose a named snapshot whose status is `READY`; record its creation time,
   source disk, project, snapshot name and release SHA. Confirm the test host is
   isolated and has no public ingress or provider credentials. **Never restore
   over the production disk as a first test.**
2. Create a new disk from the snapshot in the same zone and attach it only to
   the isolated recovery host. Example (after verifying every value against
   live GCP):

   ```sh
   gcloud compute disks create sigma-state-restore-YYYYMMDD \
     --project=APPROVED_PROJECT --zone=APPROVED_ZONE \
     --source-snapshot=READY_SNAPSHOT --type=pd-balanced
   gcloud compute instances attach-disk sigma-recovery-01 \
     --project=APPROVED_PROJECT --zone=APPROVED_ZONE \
     --disk=sigma-state-restore-YYYYMMDD --device-name=sigma-state-restore \
     --mode=ro
   ```

   Do not attach the test disk to the production VM. On the recovery host,
   identify the new device using `lsblk -f`, `blkid`, and its GCE device name;
   never format it. Mount it read-only:

   ```sh
   sudo mkdir -p /mnt/sigma-restore
   sudo mount -o ro,noload,nosuid,nodev,noexec,norecovery \
     /dev/disk/by-id/google-sigma-state-restore-YYYYMMDD /mnt/sigma-restore
   findmnt /mnt/sigma-restore
   ```

3. Run the packaged offline verifier against the mounted filesystem root. The
   verifier opens each SQLite database read-only and checks integrity/tables,
   identity-to-workspace mapping, one-to-one workspace directories, saved
   project and research artifact counts, and accounting references and
   reserved/unknown calls. For a two-user acceptance point:

   ```sh
   sudo python3 /opt/sigma/current/deploy/verify-state-restore.py \
     /mnt/sigma-restore --min-workspaces 2 --min-projects 1 \
     --min-artifacts 1 --min-papers 1
   ```

   Require every `PASS` and the final `PASS`; any `FAIL` blocks acceptance.
   Review project records and expected paper `.tex`/`.pdf`, session evidence,
   and ledger state against the known test identities using authorized,
   redacted evidence. The verifier does not start SIGMA, contact OAuth/provider
   services, repair files, or prove the browser/API on GCE. If compatibility
   testing is required, use a separately approved isolated test stack on a
   writable disposable clone with public ingress and external provider calls
   blocked; do not point it at production.
4. Record start/end UTC time, snapshot ID and creation time, new disk/device/UUID,
   release SHA, exact command, every verifier result, missing items and elapsed
   restore time. Preserve sanitized evidence before removing the temporary disk.
   Keep the snapshot until evidence is reviewed; separately authorize cleanup.
5. Production cutover is a distinct owner-approved incident action: stop all
   writers, preserve the damaged disk for investigation, detach it without
   deleting it, attach the verified restored disk, confirm UUID/fstab/mount and
   ownership, run host preflight, start `sigma.service`, and verify identity,
   isolation, saved artifacts and accounting before reopening traffic.
6. Declare the last recoverable timestamp and any data-loss interval. Treat
   interrupted provider calls as potentially charged; preserve unknown
   reservations and never reconstruct/zero the ledger to make totals look clean.
   After retaining reviewable evidence, unmount the clone before detaching it;
   delete the recovery disk only after separate owner approval:

   ```sh
   sudo umount /mnt/sigma-restore
   gcloud compute instances detach-disk sigma-recovery-01 \
     --project=APPROVED_PROJECT --zone=APPROVED_ZONE \
     --disk=sigma-state-restore-YYYYMMDD
   ```

## 7. Rollback code (not data)

**Schema 10 is a forward-only boundary for the currently available v0.1.4
binary.** v0.1.4 accepts project schemas 1–9; v0.1.5 accepts 1–10 and can
write schema 10 when saving strategy provenance including
`inference_request_id`. Therefore `--schema-compatible` is an operator
assertion, not a compatibility test. Do not use the existing v0.1.4 image as
code rollback after any v0.1.5 schema 10 write. No v0.1.4 compatibility bridge
has been implemented or tested. The rollback readiness gate remains unmet.

The safe default after a schema 10 write is forward-fix on v0.1.5-compatible
code. If service must be stopped, stop writers and preserve the post-cutover
disk and logs. If the owner chooses recovery to pre-release state, that is a
separate data restore incident: use the isolated, verified pre-cutover
snapshot, declare the data-loss interval from its creation time, preserve the
post-cutover disk for forensics, and obtain explicit owner authorization before
any production disk swap. Never imply that reverting the release pin rolls
back or preserves schema 10 data. A compatibility bridge would need its own
implementation and tests against real schema 10 fixture data before it can
change this policy.

1. Identify current and target SHAs. Confirm target images exist locally, a
   recent recovery point has passed isolated restore verification, data/schema
   compatibility has been demonstrated for the exact older binary, and no
   backup is running. If any condition is unknown, do not perform code rollback.
2. Run the guarded helper with explicit operator assertions:

   ```sh
   sudo /opt/sigma/current/deploy/rollback-gce-release.sh PREVIOUS_40_CHAR_SHA \
     --backup-verified --schema-compatible
   ```

   It refuses an unmounted disk, unsafe deploy env, active backup, invalid SHA,
   missing locally tagged images or failed host preflight. It saves the current
   root-only deploy env under `/var/lib/sigma/releases/`, atomically changes
   only `SIGMA_RELEASE`, restarts through systemd, and waits up to two minutes
   for backend/frontend healthchecks and running edge. On preflight/startup or
   health failure it restores the prior env and attempts to restart the prior
   release. It never invokes `down`, deletes images, changes the state disk or
   edits database state.
3. Regardless of helper result, verify public HTTPS/API, auth identity,
   workspace isolation, projects/artifacts, usage totals and pending
   reservations. Preserve output and journals; keep both release env records
   and images through incident review.
4. If data/schema are incompatible, pause rollout and use the separate-disk
   restore/cutover process with owner authorization and a declared data-loss
   window. No code rollback or container healthcheck proves recoverability.

## 8. Operational access and user incidents

- **Invite/revoke account:** Use approved admin access-management UI/API. Confirm requested Google identity and least privilege. Revoke access without deleting workspace; verify denied access afterward.
- **Suspected privacy leak:** Stop public access, preserve logs and disk evidence securely, revoke compromised credentials, isolate affected accounts and escalate immediately. Do not circulate affected records.
- **Compromised OAuth/provider secret:** Revoke/rotate in Google/Secret Manager/provider; update approved secret files, restart, verify and audit. Never include secret payload in a ticket.
- **Quota or provider failure:** Fail closed, inspect reservation/unknown-charge accounting, do not force-retry or reset usage. Resolve via existing admin procedure or escalate.
- **DNS/TLS outage:** Check DuckDNS record vs reserved VM IP, ingress rules, Caddy certificate status, clock and DNS propagation before changing secrets or deleting cert data.
- **Low disk / state corruption:** Stop new research, inspect filesystem/mount and backups. Do not delete workspaces or SQLite files as a quick fix. Recover using verified snapshot.
- **Incident documentation:** Record timeline, affected components, mitigation, data-integrity assessment, owner notifications, verification and follow-up issue.

## 9. Recurring operations

| Frequency | Check |
| --- | --- |
| Daily | Site HTTPS/health; disk/mount/space; backup completion; service/rootless daemon; critical errors |
| Weekly | Verify backup retention and recovery-point inventory; review authorized users, usage/limits and security updates |
| Monthly or after meaningful data changes | Non-production restore drill, including workspace separation and SQLite integrity |
| Every release | Tests, release SHA, backup, preflight, desktop smoke, rollback readiness |
| After infrastructure change | Re-run rootless isolation, firewall, IAM, disk mount, OAuth and hosted feature checks |

## 10. Completion record template

```text
Operation:
UTC timestamp / operator:
GCP project / VM / release SHA:
Affected users / downtime:
Preflight and backup recovery point:
Commands / tests actually run (redacted):
Observed outcome (PASS / FAIL / BLOCKED):
Data/identity/usage integrity:
Rollback action or follow-up issue:
```

**Maintenance rule:** Any recurring operational action discovered during Cloud deployment or incidents gets a tested step here before it is considered operationally handed off.

## SIGMA keyless release identities (2026-11-06; Issue #590)

The release operator uses short-lived service-account impersonation, not
downloadable service-account keys. The human operator's existing project
`roles/owner` binding is preserved. The two release service accounts have no
project Owner/Editor binding and no user-managed keys:

| Identity | Scope and purpose |
| --- | --- |
| `sigma-release-operator@sigma-research-prod.iam.gserviceaccount.com` | Snapshot `sigma-state`, build and inspect isolated recovery resources, and use OS Login on release-prefixed recovery VMs. |
| `sigma-release-ssh@sigma-research-prod.iam.gserviceaccount.com` | IAP and OS Login administrative access to `sigma-gce-01` only. It cannot create, delete, attach to, or change the service account on Compute resources. |

The active human operator has `roles/iam.serviceAccountTokenCreator` on each
release service account resource only. This permits short-lived impersonation
tokens; it does not create a key file. The host-only `sigma-release-ssh`
principal has `roles/iam.serviceAccountUser` on
`sigma-runtime@sigma-research-prod.iam.gserviceaccount.com` only. OS Login
requires this grant because the production VM runs as `sigma-runtime`. The
host-only identity has no instance creation or service-account attachment
permission, so it cannot attach `sigma-runtime` to another VM. The recovery
operator has no `iam.serviceAccounts.actAs` grant on `sigma-runtime`.

Project custom roles and IAM Conditions enforce the following boundaries:

- `sigmaGceSnapshotOperator` can read `sigma-state`, create a snapshot from
  that disk, and inspect/list snapshots. IAM permission alone does not make a
  snapshot application-consistent; the documented backup procedure must stop
  writers and sync the mounted state disk first. Its condition allows snapshot
  creation only from `sigma-state` and snapshot resources whose names start
  `sigma-state-v021-pre-`.
- `sigmaGceRecoveryCreator` can create only `sigma-state-restore-*` or
  `sigma-v021-recovery-*` disks and `sigma-v021-recovery-*` instances.
- `sigmaGceRecoveryOperator` can attach/detach/use/delete only those
  release-prefixed disks and instances and use only a matching pre-release
  snapshot. It cannot delete the production state disk or production VM.
- `sigmaGceRecoveryDiscovery` and `sigmaGceProjectReader` provide read-only
  project, network, subnet, image, machine type, zone, operation, instance, and
  disk inventory needed by the guarded operator workflow.
- `sigmaGceRemoteAdmin` grants `compute.instances.osLogin` and
  `compute.instances.osAdminLogin` to the host-only identity for `sigma-gce-01`
  and to the recovery identity only for `sigma-v021-recovery-*` instances.
- `sigmaIapSshOperator` grants only `iap.tunnelInstances.accessViaIAP`. The
  host identity is scoped to `sigma-gce-01` by name and instance ID. Because
  future recovery instance IDs are assigned by GCE, the recovery identity's
  IAP binding is limited to the `us-west1-b` tunnel zone. OS Login remains
  limited to recovery-prefixed instances, and recovery VMs have no service
  account or external IP.

For the 2026-11-06 setup, checks using the actual impersonated identities
confirmed: no service-account keys; no Owner/Editor role on either release
identity; the owner's Owner grant remains; snapshot permission on `sigma-state`
granted to the recovery identity and denied to the host-only identity; disk
delete permission on `sigma-state` denied; OS Admin Login granted to the
host-only identity on `sigma-gce-01` and denied to the recovery identity; VM
delete and service-account-change permissions denied to the host-only identity
on production; service-account-change permission denied to the recovery
identity on production; and IAP permission granted for the host. An SSH key
with a five-minute OS Login TTL was removed locally after an actual IAP + OS
Login SSH session succeeded, including `sudo -n true`.

The November 6 setup verified role boundaries and one ephemeral host SSH
session, but the subsequent v0.2.1 release exposed an effective-access failure:
`gcloud compute ssh` required `compute.instances.get`, which was then denied for
the release identities. Direct SSH also timed out; the project Owner ultimately
used IAP for cutover. During the authorized v0.2.2 deployment on November 8,
the required instance-read permission was effective in practice for
`sigma-release-ssh` on `sigma-gce-01` and for `sigma-release-operator` on the
temporary recovery VM. Both identities completed actual IAP/OS Login sessions
and noninteractive `sudo -n true`; the recovery identity also completed the
bounded snapshot and temporary resource lifecycle. No IAM policy change or
Owner fallback was used for that deployment. See the v0.2.2 outcome below.

One narrower limitation remains: `sigma-release-operator` lacks
`compute.globalOperations.get`. A synchronous `gcloud` create/poll command can
therefore report 403 after the operation has been accepted. In the v0.2.2
drill, named resources were verified through resource-specific reads and
short-lived impersonated API requests; no failed command was blindly retried
and no resource was recreated. A future IAM change, if selected, should add
only a justified read-only operation-status permission; never use Owner/Editor
or a long-lived key.

The November 6 setup itself did not create recovery resources. The first
bounded keyless snapshot and isolated restore drill completed during the
authorized v0.2.2 deployment documented below.

## SIGMA v0.2.2 deployment outcome (2026-11-08 UTC)

Issue #667 authorized the routine v0.2.2 release after PR #670 merged.
Production was running v0.2.1 before this release. The frozen target was merged
`main` SHA `469c955dfadb5a7bd17b72fc069a3365b4f20ba7`; its tree
`0c8513bae7be8decc27101e2e05147bbac162c8d` is identical to PR candidate SHA
`e5de6f05ef8a8976fffec4a1b6cc54aa9078f205`.

Exact merged-SHA source checks:

- [Ruff](https://github.com/bkramerext/sigma/actions/runs/42495800722) passed.
- [SIGMA verification](https://github.com/bkramerext/sigma/actions/runs/42495800717) passed.
- [Frontend build](https://github.com/bkramerext/sigma/actions/runs/42495800735) passed.
- Merged-SHA [Browser verification](https://github.com/bkramerext/sigma/actions/runs/42495800771) attempt 1 completed every browser acceptance step successfully, then the `setup-uv` post-job cache prune timed out after a 300-second cache-lock wait. Attempt 2 was cancelled during the Project Types step. The complete browser workflow passed on the identical source tree at PR SHA `e5de6f05ef8a8976fffec4a1b6cc54aa9078f205` in [run 42457938746](https://github.com/bkramerext/sigma/actions/runs/42457938746). No full suite or moving-`main` workflows were rerun.

### Keyless access and recovery

Effective access was verified with short-lived impersonation, not inferred from
role configuration. `sigma-release-ssh` described `sigma-gce-01`, connected
over IAP/OS Login, and passed `sudo -n true`. `sigma-release-operator`
described the temporary recovery VM, connected over IAP/OS Login, and passed
`sudo -n true`; it created and inspected the source snapshot, created the clone
disk and VM, attached/detached the clone, and deleted the recovery VM and disks.
No Owner fallback, broad IAM grant, long-lived key, or production-data edit was
used. The targeted `compute.instances.get` checks passed on the production VM
for `sigma-release-ssh` and on the release-prefixed recovery VM for
`sigma-release-operator`.

The recovery identity lacks `compute.globalOperations.get`. The label-free
snapshot request succeeded and the snapshot reached READY, but synchronous
`gcloud` polling returned 403 after submitting the operation. The accepted
operation and named resource were checked using short-lived impersonated API
requests and resource-specific reads; no operation or resource was retried or
recreated. Exact billing totals also remain unreadable because
`cloudbilling.googleapis.com` is disabled. The temporary footprint was one
30 GB clone, one 10 GB boot disk, one `e2-standard-2` VM for under 12 minutes,
and one snapshot whose reported storage is 35,513,600 bytes. A conservative
published-rate estimate is below $2 for the first month including a full 30 GB
snapshot, well within the $25 incremental ceiling. Exact billed spend was not
queried.

The fresh application-consistent snapshot
`sigma-state-v021-pre-20261108-1546`, ID `6224195028464248741`, was created
from `sigma-state` at 2026-11-08 15:46:18 UTC and remains READY/retained. SIGMA
was stopped and the mounted state filesystem synced from 15:46:10 to 15:46:45
UTC (about 35 seconds). The 30 GB clone, ID `6890385674874988321`, was attached
READ_ONLY to an isolated VM with no public IP and no service account. The
recovery VM had OS Login and blocked project SSH keys at creation. Its first
IAP attempt showed that the project's existing IAP-only firewall targets
network tag `sigma-iap-ssh`; that existing tag was added to the temporary VM.
The state filesystem UUID matched production and mounted read-only with
`ro,nosuid,nodev,noexec,norecovery` (the kernel reports `norecovery` for the
requested ext4 `noload` behavior). The verifier from the exact release SHA
(SHA-256 `1f0f7c7916cc2265784b8dda63993500240ef2d293820470c05e765e8fca049a`)
passed all checks: 3 SQLite integrity checks, 3 identities/mappings, 17
projects, 42 artifacts, one TeX/PDF paper with matching hash/size, 10 terminal
job-history rows, and 46 accounting rows ($5.938237 recorded/reserved; 15
reserved or unknown outcomes). The recovery VM, its auto-deleted boot disk,
clone disk, mount, and temporary OS Login keys were removed and confirmed
absent. Only the READY snapshot was retained.

### Guarded deployment and verification

The release command was:

```sh
sudo python3 /opt/sigma/current/deploy/deploy-gce-release.py \
  469c955dfadb5a7bd17b72fc069a3365b4f20ba7 \
  --backup-verified --schema-compatible
```

The helper ran from 16:01:31 to 16:03:35 UTC, built both images from the
selected SHA, and confirmed container health, release identity, and the state
mount. Systemd stopped the old stack at 16:03:05 and started the new stack at
16:03:10. Caddy entered and exited maintenance at 16:03:05 and 16:03:35 UTC;
the observed public maintenance window was 30 seconds. The release record
`/var/lib/sigma/releases/469c955dfadb5a7bd17b72fc069a3365b4f20ba7.json`, host
checkout, protected release pin, image labels, and About build agree on the
full SHA.

| Image | Immutable image ID | `org.opencontainers.image.revision` |
| --- | --- | --- |
| Backend | `sha256:1673bf9eedbdf81aa9f9d9944eb3a8708bc1cd10b77d0add1b64afea83f0096c` | `469c955dfadb5a7bd17b72fc069a3365b4f20ba7` |
| Frontend | `sha256:94721b300106d117b09330092b62797432a3f0d7abf57a195331a00ca65af911` | `469c955dfadb5a7bd17b72fc069a3365b4f20ba7` |

Post-deployment checks passed: `sigma.service` active; backend, frontend, and
edge containers healthy; maintenance snippet absent; state UUID
`28ef67cb-4da8-46e7-9a8b-dce0470153a5` mounted at `/srv/sigma-state` with
`rw,nosuid,nodev,noexec,relatime`; post-deployment data verifier matched the
pre-release aggregate baseline; public HTTPS root and endpoint probe passed;
hosted `/api/cloud-auth/status` returned HTTP 200/ready; anonymous
`/api/health` returned its expected HTTP 401. The served frontend bundle's
About component renders `Version 0.2.2 · Build 469c955`. No paid inference was
run, and user, project, research, paper, authorization, and accounting records
were preserved.

### Remaining limits and rollback

The browser workflow's merged-SHA job conclusion is limited by its post-job
cache cleanup failure, although all acceptance steps passed and the identical
tree has a complete successful browser run. The Cloud Billing API remains
disabled, so exact current spend is unavailable. Auth readiness passed, but an
authenticated Google sign-in and account-dependent import/export, email,
research, and saved-paper flows were not exercised. The daily backup timer
remains absent; the retained snapshot is a one-off recovery point. A code
rollback does not roll back data. Preserve new writes and verify the old
binary's compatibility with live schemas before rolling back; the retained
snapshot predates v0.2.2 and is reserved for separately authorized data
recovery.

## SIGMA v0.2.1 deployment outcome (2026-11-06 PDT / 2026-11-07 UTC)

Issue [#588](https://github.com/bkramerext/sigma/issues/588) authorized a
routine production deployment of SIGMA v0.2.1 from exact SHA
`5435e14eeea159ab207ad50016577b9a9542ae59`. The Nov 6 release-scope decision
was followed: PR #639, PR #641, issue #643, and new Research Ethos work are
excluded. Exact-SHA Ruff, SIGMA verification, and browser verification had
passed before this deployment. Local `./sigma test` passed on the exact SHA.

Billing was confirmed enabled through the already-authorized human account and
quota was reviewed. The keyless operator/SSH IAM split remained in place, with
no role broadening during deployment. The operator identity did not have
`compute.instances.get` for `gcloud compute ssh` discovery, and direct SSH
timed out; the existing authorized project admin ran the deployment over IAP.
This was an access-path friction only; the runbook helper and guards were not
bypassed.

### Recovery point and restore verification

Before cutover, production writers were stopped, the application-consistent
snapshot `sigma-state-v021-pre-20261107-0658` was created from `sigma-state` in
`us-west1-b`, and it reached READY with 436,288 stored bytes. The isolated
recovery VM had no public IP or service account. Its clone disk was attached
read-only and mounted with
`ro,noload,nosuid,nodev,noexec,norecovery`. The read-only verifier passed three
SQLite integrity checks; three identity/workspace mappings; 17 project
records; 42 research artifacts; one TeX/PDF pair with matching PDF hash and
size; ten terminal history rows across two unmapped historical workspaces; and
46 accounting rows with $5.938237 recorded/reserved and 15 reserved or unknown
outcomes. It ended with `PASS: all restore checks completed read-only`.

The first verifier run found a known
`.publication-reference-compilation.json` cache in a paper directory and
mistook it for a paper record. The operational verifier was narrowly updated
to validate that exact cache schema and its SHA-256 seal, exclude it from paper
and artifact counts, and continue strict checking of actual paper records.
The cached record reports an uncertain prior attempt and fallback; no provider
call was replayed. Verification then passed. The production snapshot remains
retained. The temporary VM and clone disk were deleted and confirmed absent.

### Cutover and production smoke

The guarded helper ran against the exact SHA with `--backup-verified
--schema-compatible` and no `--no-build`. It built both application images from
the approved commit. Systemd recorded the release start at 07:08:51 UTC; both
app containers became healthy at 07:09:01 UTC and systemd completed at
07:09:02 UTC. Host Caddy reloaded with maintenance off at 07:09:09 UTC. The
observed public maintenance/cutover window was about 20 seconds, from
07:08:49–07:09:09 UTC.

Backend image ID and digest:
`sha256:1ab6ae4c60f8c320bb69c1cc0135a60b994084befa7dc0c440701a8fa2cd3a88`.
Frontend image ID and digest:
`sha256:4615bc091f737620956a5da1bedc3f96ced3a38c4d155e513a126b670f1f09e5`.
Both labels and the release record at
`/var/lib/sigma/releases/5435e14eeea159ab207ad50016577b9a9542ae59.json` match
the exact source SHA. Edge image ID remains
`sha256:cf1bd22f2415bc99b785ece1df2c49d32985ac4ac42d84df335be17350593693`.
The host checkout is at the approved SHA; `sigma.service` is active with no
pending daemon reload, and backend, frontend, and edge containers are healthy.
The persistent disk remains mounted at `/srv/sigma-state` from `/dev/sdb`, UUID
`28ef67cb-4da8-46e7-9a8b-dce0470153a5`, with `rw,nosuid,nodev,noexec,relatime`.
The maintenance snippet is absent (maintenance off).

External checks: `https://sigma-research.duckdns.org/` returned HTTP 200;
`/api/cloud-auth/status` returned HTTP 200 with `enabled=true`, `ready=true`,
and `target=hosted`; unauthenticated `/api/health` returned the expected HTTP
401. Headless Chrome rendered the app with title `SIGMA · Research workspace`
and About showed `Version 0.2.1 · Build 5435e14`; there were no page errors or
non-read-only requests. Production SQLite integrity checks passed after
deployment and identity/workspace/job/accounting row counts were readable.
No user project, paper, session, authorization, or accounting records were
deleted or reset; only three verified zero-byte orphaned research scheduler
slot-lock markers were removed before the fresh snapshot, after confirming
their workspace had no project/job/call references. No paid inference or
research execution was initiated.

### Remaining limits and rollback

Positive authenticated login, project import/export, actual email delivery,
bounded research execution, and opening a saved paper were not exercised; no
authenticated production browser session was available and paid inference was
out of scope. The recurring backup timer remains absent, so this retained
snapshot is a one-off recovery point, not a backup policy. Exact GCP-billed
recovery-drill spend was not independently queried; planned incremental
resources stayed within the documented $25 ceiling. A code rollback does not
roll back data. The snapshot predates the deployment and remains preserved;
before any rollback, confirm the old binary can read the live state and preserve
new writes, or treat it as a separately authorized data-recovery incident.

## SIGMA v0.2.0 deployment outcome (2026-11-04 PDT)

**Operator:** Red, acting under the operator's explicit authorization in this
conversation. **Target:** merged `main` commit
`9d938907ffd02fb89c9d10545e8df61484310cbd` (v0.2.0). The exact target passed
[SIGMA test shards](https://github.com/bkramerext/sigma/actions/runs/41977490940),
[browser acceptance](https://github.com/bkramerext/sigma/actions/runs/41977490915),
and [Ruff](https://github.com/bkramerext/sigma/actions/runs/41977490887).
Deployment used the documented guarded helper:

```sh
sudo python3 /opt/sigma/current/deploy/deploy-gce-release.py \
  9d938907ffd02fb89c9d10545e8df61484310cbd \
  --backup-verified --schema-compatible
```

The helper reported success after verifying container health, the service
release, and state mount. It built the backend and frontend from the exact
target commit. Backend image ID is
`sha256:65572961183f12569854e5c0ee4c63744441dd616f1b37ed72caaa0490b7c750`;
frontend image ID is
`sha256:f2cb44d69a8a2b82d0596eca59b5a8880f360840adb964b4812981ef96093a4e`.
The release record at
`/var/lib/sigma/releases/9d938907ffd02fb89c9d10545e8df61484310cbd.json`
contains the matching source SHA and running image IDs. Protected release pin
and host checkout match the target. `sigma.service` and host Caddy are active;
backend, frontend, and edge containers are healthy. `/srv/sigma-state` is
mounted from `/dev/sdb` as ext4 with `rw,nosuid,nodev,noexec,relatime`.
Maintenance is off. The service stop began 2026-11-05 06:07:16 UTC and systemd
reported the active start at 06:07:32 UTC. The public HTTPS root returned HTTP
200; unauthenticated `/api/health` returned the expected HTTP 401.

### Recovery point and restore drill

Before deployment, production writers were stopped, the application-consistent
snapshot `sigma-state-v020-pre-20261104-1736` was created from `sigma-state`
in `us-west1-b`, and the snapshot reached READY at
2026-11-04 21:46:57 PDT. The source VM's service identity could not list
snapshots, so the documented operator GCP credentials path was used; no IAM
grant was made. A temporary recovery VM had no external IP or service account.
Its clone disk was attached read-only and mounted with
`ro,noload,nosuid,nodev,noexec,norecovery`.

The offline verifier passed all existing aggregate thresholds: three SQLite
integrity checks; three identity/workspace mappings and directories; 14
projects; 33 artifacts; zero saved PDF/TeX pairs; 10 terminal job-history rows
across two unmapped workspaces; and 19 accounting rows with $1.218456 recorded
or reserved and six reserved/unknown outcomes preserved. It returned
`PASS: all restore checks completed read-only`. The temporary VM and clone disk
were detached, deleted, and verified absent. The recovery snapshot remains
retained. The restore drill is read-only evidence, not a production restore.

### Production smoke outcome

Headless Chrome using the installed Chrome executable loaded the production
root (HTTP 200; title `SIGMA · Research workspace`), dismissed the normal
first-visit guest welcome in an isolated browser context, and read About as
`Version 0.2.0 · Build 9d93890`. `/api/cloud-auth/status` returned 200 and an
unauthenticated recent-projects request returned 401. No POST or provider call
occurred from the About/anonymous smoke. OAuth login reached Google's sign-in
redirect; no credentials were submitted. A public sample research project and
its history view loaded in a temporary guest workspace; no research session
was started and no provider request was made.

The deployment is **live and healthy**, but full production smoke acceptance is
**incomplete**. Because no authenticated production session was available,
positive account login, project import/export, actual email delivery, execution
of a bounded research session, and viewing a saved paper were not verified.
The restore baseline contained zero saved PDF/TeX paper pairs. No paid provider
call or research execution was initiated, consistent with the deployment
constraint. Do not report those cases as passed. No production data, secrets,
or configuration were changed; this release made no application schema
migration.

The target includes PR #548's v0.2.0 metadata and PR #549's correction to the
deployment runbook: the guarded helper has no `--no-build` option and builds
the exact SHA internally before stopping/pinning the service. The release
therefore followed the established helper process.

## T128 host-readiness and T129 exact-SHA release procedure

Before the first application start, follow [T128 host readiness](T128_HOST_READINESS.md) and [T128 live-readiness evidence](T128_LIVE_READINESS.md). Host identity, state-disk UUID/mount options, rootless Docker, service dependencies, container restrictions, and effective GCE firewall rules must be observed on the actual VM; source inspection alone is not a PASS.

The release operator must use a full lowercase 40-character commit SHA. The deployment command builds backend and frontend images from an exported Git archive of that exact commit using `deploy/release_image.py`, labels and verifies their source SHA, and records immutable image IDs/digests after healthy startup. It must not build the requested tag from the currently checked-out release. Initial start:

```sh
sudo python3 /opt/sigma/current/deploy/deploy-gce-release.py FULL_40_CHAR_SHA --initial
```

Upgrade (only after verifying a recovery point and exact target/rollback
compatibility; for schema 10, the v0.1.4 fallback is not compatible):

```sh
sudo python3 /opt/sigma/current/deploy/deploy-gce-release.py FULL_40_CHAR_SHA \
  --backup-verified --schema-compatible
```

Do not run these commands until T128 host checks, production configuration/secret delivery, and the coordinator's explicit deployment authorization are complete. A local rehearsal does not constitute hosted acceptance.
