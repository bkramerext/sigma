# SIGMA Operations Runbook

**Status:** Operator procedures for the GCE deployment at `sigma-research.duckdns.org`. Keep this document current as deployment is exercised. **Do not treat proposed commands as executed evidence.**

The detailed configuration and exact provisioning parameters live in [CLOUD_DEPLOYMENT.md](CLOUD_DEPLOYMENT.md). This runbook is the short operational entry point. Record the deployed commit, tested command, outcome, operator, date and any deviation after performing each operation. No secrets, access tokens or user data in logs, PRs or chat.

## Deployment inventory and operator evidence (T127)

This runbook and [CLOUD_DEPLOYMENT.md](CLOUD_DEPLOYMENT.md#cloud-resource-inventory-t127) are the maintained records. The deployment coordinator records actual IDs, resource creation, verification results, dates, and deviations as the operator supplies evidence. **The operator should not need to maintain a separate checklist or remember identifiers.** Proposed resource names must not be presented as live resources.

| Item | Current record | Verification |
| --- | --- | --- |
| Google OAuth project | `SIGMA Auth`; ID `sigma-auth-512601`; number `665111821572` | Operator read from Cloud Console, 2026-10-25 |
| Infrastructure project | `SIGMA Production`; ID `sigma-research-prod`; number `224387813390` | Operator-reported created in Cloud Console, 2026-10-25; billing/permissions pending verification |
| DNS hostname | `sigma-research.duckdns.org` (DuckDNS) | A resolves to `136.66.128.82`; public HTTPS/API probe passed 2026-10-26 |
| Zone and VM | `us-west1-b`; `sigma-gce-01`, Ubuntu 24.04 amd64, `e2-standard-2` | RUNNING; IAP/OS Login verified 2026-10-26 |
| Disk | `sigma-state` 30 GB `pd-balanced`, zonal `us-west1-b`; boot disk 100 GiB `pd-standard` | Attached, mounted with approved UUID/options; one-off recovery snapshot READY 2026-10-26 |
| Network | `sigma-vpc`, subnet `sigma-us-west1` in `us-west1`, primary IPv4 `10.42.0.0/24`; static external IPv4 `sigma-web-ip` = **`136.66.128.82`** (Premium, regional) | Attached to VM; public DNS and HTTPS routing verified 2026-10-26 |
| VM identity and access | `sigma-runtime` service account; IAP SSH with OS Login | VM identity and IAP access verified 2026-10-26; worker IAM remains broader than least privilege |
| Billing account | `My Billing Account`; ID `015C1D-E6B877-9913D6`; Direct, Active; last 30 days spend $0 | Operator screenshot, 2026-10-25; production project association unverified |
| Billing / alert | Trial/billing link and $300 project budget | Not yet verified |
| Production release | `e1ef8db8ea6c15bcb79ad9c8d06e8e5f6f4527f3` | Deployed and endpoint-verified 2026-10-26; formal acceptance pending |

**Change log**

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

**Prerequisites:** Explicit approved GCP project/resources, IAM, static IP, state disk, Secret Manager configuration, production Google OAuth Web client and DuckDNS access.

1. Follow [Cloud Deployment: Google setup and operator commands](CLOUD_DEPLOYMENT.md#google-setup-and-operator-commands) and the provisioning runbook there. Provision Ubuntu 24.04 amd64 in `us-west1-b` with a separately retained state disk (`auto-delete=no`). Restrict SSH to approved IAP path, public ingress to 80/443 when ready.
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
6. Run `sudo /usr/local/libexec/sigma/gce_preflight.py --json`; proceed only on PASS/exit 0. Run `python -m sigma.cloud_runtime_check` against the **actual rootless** daemon without development overrides.
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
   sudo /usr/local/libexec/sigma/gce_preflight.py --json
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

1. Confirm candidate full Git SHA, reviewed PR, verified tests/browser evidence, and known migrations. Ensure backup/restore point is current.
2. From a repository checkout with the candidate commit available, build release images using `python3 /path/to/checkout/deploy/release_image.py build /path/to/checkout FULL_40_CHAR_SHA`. This exports the requested commit from Git, so dirty files and the checkout's current HEAD are not build inputs. The command fails if the exact commit cannot be resolved. Inspect the generated `sigma-backend:SHA` and `sigma-frontend:SHA` image labels before proceeding. If the sandbox image source changed, rebuild the rootless Python/Sage images.
3. Announce maintenance; stop production via `sudo systemctl stop sigma.service` before a consistent data snapshot (see next section).
4. Update `SIGMA_RELEASE` in protected `/etc/sigma/deploy.env` to that same full SHA. Do not change state volume mapping or delete Compose volumes.
5. Run preflight; start via `sudo systemctl start sigma.service`. Startup verifies both image source labels and uses Compose `--no-build`; it records the source commit, actual running container IDs, immutable image IDs and any repository digests in `/var/lib/sigma/releases/SHA.json`. Verify that record and the running containers, then verify auth, existing users, project/session persistence, bounded research, exports and HTTPS.
6. If verification fails, use rollback below. Record SHA, downtime, tests and outcome.

## 5. Daily state-disk backup

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
     --disk=sigma-state-restore-YYYYMMDD --device-name=sigma-state-restore
   ```

   Do not attach the test disk to the production VM. On the recovery host,
   identify the new device using `lsblk -f`, `blkid`, and its GCE device name;
   never format it. Mount it read-only:

   ```sh
   sudo mkdir -p /mnt/sigma-restore
   sudo mount -o ro,noload,nosuid,nodev,noexec \
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

1. Identify the current and target SHAs. Confirm target images exist locally, a
   recent recovery point is verified, the rollback is compatible with current
   data/schema, and no backup is running. If compatibility is unknown, stop and
   escalate; a code rollback never rewinds SQLite or provider charges.
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

## T128 host-readiness and T129 exact-SHA release procedure

Before the first application start, follow [T128 host readiness](T128_HOST_READINESS.md) and [T128 live-readiness evidence](T128_LIVE_READINESS.md). Host identity, state-disk UUID/mount options, rootless Docker, service dependencies, container restrictions, and effective GCE firewall rules must be observed on the actual VM; source inspection alone is not a PASS.

The release operator must use a full lowercase 40-character commit SHA. The deployment command builds backend and frontend images from an exported Git archive of that exact commit using `deploy/release_image.py`, labels and verifies their source SHA, and records immutable image IDs/digests after healthy startup. It must not build the requested tag from the currently checked-out release. Initial start:

```sh
sudo python3 /opt/sigma/current/deploy/deploy-gce-release.py FULL_40_CHAR_SHA --initial
```

Upgrade (only after verifying a recovery-point backup and schema compatibility):

```sh
sudo python3 /opt/sigma/current/deploy/deploy-gce-release.py FULL_40_CHAR_SHA \
  --backup-verified --schema-compatible
```

Do not run these commands until T128 host checks, production configuration/secret delivery, and the coordinator's explicit deployment authorization are complete. A local rehearsal does not constitute hosted acceptance.
