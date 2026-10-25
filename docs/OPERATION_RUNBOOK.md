# SIGMA Operations Runbook

**Status:** Operator procedures for the GCE deployment at `sigma-research.duckdns.org`. Keep this document current as deployment is exercised. **Do not treat proposed commands as executed evidence.**

The detailed configuration and exact provisioning parameters live in [CLOUD_DEPLOYMENT.md](CLOUD_DEPLOYMENT.md). This runbook is the short operational entry point. Record the deployed commit, tested command, outcome, operator, date and any deviation after performing each operation. No secrets, access tokens or user data in logs, PRs or chat.

## Deployment inventory and operator evidence (T127)

This runbook and [CLOUD_DEPLOYMENT.md](CLOUD_DEPLOYMENT.md#cloud-resource-inventory-t127) are the maintained records. The deployment coordinator records actual IDs, resource creation, verification results, dates, and deviations as the operator supplies evidence. **The operator should not need to maintain a separate checklist or remember identifiers.** Proposed resource names must not be presented as live resources.

| Item | Current record | Verification |
| --- | --- | --- |
| Google OAuth project | `SIGMA Auth`; ID `sigma-auth-512601`; number `665111821572` | Operator read from Cloud Console, 2026-10-25 |
| Infrastructure project | `SIGMA Production`; ID `sigma-research-prod`; number `224387813390` | Operator-reported created in Cloud Console, 2026-10-25; billing/permissions pending verification |
| DNS hostname | `sigma-research.duckdns.org` (DuckDNS) | Registered; A record target not yet confirmed |
| Zone and VM | `us-west1-b`; planned `sigma-gce-01`, Ubuntu 24.04 amd64, `e2-standard-4` | Provisioning pending |
| Disk | Planned `sigma-state` 200 GiB `pd-balanced`, retained; boot 100 GiB `pd-standard` | Provisioning and UUID verification pending |
| Network | Planned `sigma-vpc`, subnet `sigma-us-west1`, proposed `10.42.0.0/24`, static IP name `sigma-web-ip` | CIDR and resource creation pending |
| VM identity and access | Planned `sigma-runtime` service account, secret-scoped access; IAP SSH with OS Login | Creation and live IAM verification pending |
| Billing account | `My Billing Account`; ID `015C1D-E6B877-9913D6`; Direct, Active; last 30 days spend $0 | Operator screenshot, 2026-10-25; production project association unverified |
| Billing / alert | Trial/billing link and $300 project budget | Not yet verified |
| Production release | Exact Git SHA and live host evidence | Not deployed |

**Change log**

- 2026-10-25: Operator screenshot showed active Direct billing account `My Billing Account` (`015C1D-E6B877-9913D6`) and $0 spend over 30 days. Project linkage and free trial remain unverified.

- 2026-10-25: Operator created `SIGMA Production`, ID `sigma-research-prod`, project number `224387813390`. Billing and permissions have not yet been verified.

- 2026-10-25: Operator reported existing `SIGMA Auth` project identity (name, project ID, project number). Confirmed selected DuckDNS hostname from approved deployment documentation. No production resources, IAM grants, billing changes, or DNS updates executed by this documentation change.

## Before any operation

1. Identify the GCP project, `us-west1-b` zone, VM `sigma-gce-01`, disk `sigma-state`, public hostname, and current `SIGMA_RELEASE`. Confirm these against **live GCP**, not just this document.
2. Identify impact: read-only, write, downtime, user data, security, external resources or provider calls. Obtain owner authorization for material changes. Warn users before downtime.
3. Confirm healthy **recent recoverable backup** before deployment, migration or restoration. Never operate on an unverified disk, or run `gcloud` commands with unresolved placeholders.
4. Verify `/srv/sigma-state` is the **attached persistent disk**, mounted with expected filesystem UUID and restrictive permissions. **Never fall back to boot/container storage**.
5. Prefer `sudo systemctl ... sigma.service` for the production application. Do **not** run production Compose `up` manually, mount a rootful Docker socket, or use `--allow-nonrootless-dev` for acceptance.

## 1. Provision a new host (once per VM)

**Prerequisites:** Explicit approved GCP project/resources, IAM, static IP, state disk, Secret Manager configuration, production Google OAuth Web client and DuckDNS access.

1. Follow [Cloud Deployment: Google setup and operator commands](CLOUD_DEPLOYMENT.md#google-setup-and-operator-commands) and the provisioning runbook there. Provision Ubuntu 24.04 amd64 in `us-west1-b` with a separately retained state disk (`auto-delete=no`). Restrict SSH to approved IAP path, public ingress to 80/443 when ready.
2. Confirm disk identity and UUID before initial filesystem setup. **Never format an existing disk**. Mount persistently at `/srv/sigma-state`; verify owner, permissions and systemd mount ordering.
3. Stage reviewed code at `/opt/sigma/current` and run `sudo /opt/sigma/current/deploy/install-gce-host.sh`. Install/configure the dedicated `sigma-sandbox` rootless Docker daemon.
4. Build Python and Sage runner images **under the rootless daemon** using `deploy/build-sandbox-images.sh`, as described in the Cloud Deployment host setup contract.
5. Set `/etc/sigma/deploy.env` with release SHA, domain, OAuth client ID, approved limits and secret-file paths; protect it `root:root 0600`. Use `deploy/fetch-secrets.sh` for named secrets. Never print secret values.
6. Run `sudo /usr/local/libexec/sigma/gce_preflight.py --json`; proceed only on PASS/exit 0. Run `python -m sigma.cloud_runtime_check` against the **actual rootless** daemon without development overrides.
7. Configure DuckDNS A record to the reserved static IP; verify external DNS and HTTPS/Caddy certificate. Set Google OAuth allowed origin `https://sigma-research.duckdns.org` and callback `https://sigma-research.duckdns.org/api/cloud-auth/callback`.
8. Start with `sudo systemctl enable --now sigma.service`. Check Caddy/API/frontend health, auth mode, private state mounts, logs and research sandbox isolation. Record actual endpoint results.
9. Complete hosted acceptance before inviting users: two distinct Google identities, unauthorized access rejection, workspace isolation, bounded sponsored inference, Python/Sage, sessions/recovery, Markdown/TeX/PDF/report export, browser restart and data persistence. **Desktop browser is the release target; mobile-specific acceptance is out of scope.**

## 2. Routine health and diagnosis

Use read-only commands on host:

```sh
sudo systemctl status sigma.service --no-pager
sudo systemctl status 'srv-sigma\x2dstate.mount' --no-pager
findmnt /srv/sigma-state
sudo /usr/local/libexec/sigma/gce_preflight.py --json
sudo journalctl -u sigma.service -n 100 --no-pager
```

Verify public HTTPS, `/api` routing and application health with the documented probe, not only process status. Redact tokens, personal data and request bodies from captured logs. For failure classify DNS/TLS, VM/network, disk mount, Docker/rootless socket, service, OAuth, secret access, quota, provider or persistent state before restarting.

## 3. Restart service / recover after VM reboot

1. Check state disk mount and preflight first; **do not start** if storage is absent or permissions differ.
2. `sudo systemctl restart sigma.service`; check `systemctl status`, logs, HTTPS and app health.
3. Verify existing saved project, sessions, paper artifacts, Google subject mapping and usage ledger remain intact.
4. Treat interrupted provider calls as **uncertain** and retain pending reservations. Never replay billable requests or edit the usage ledger to make the UI look healthy.
5. For VM reboot, verify the disk mount, sandbox daemon and `sigma.service` started in correct order; redo steps 2–4.

## 4. Application release / update

1. Confirm candidate Git SHA, reviewed PR, verified tests/browser evidence, and known migrations. Ensure backup/restore point is current.
2. Stage new checkout and approved images; inspect pinned image versions and any schema/data migrations. If the sandbox image source changed, rebuild the rootless Python/Sage images.
3. Announce maintenance; stop production via `sudo systemctl stop sigma.service` before a consistent data snapshot (see next section).
4. Update `SIGMA_RELEASE` in protected `/etc/sigma/deploy.env` and stage corresponding images/code. Do not change state volume mapping or delete Compose volumes.
5. Run preflight; start via `sudo systemctl start sigma.service`; verify auth, existing users, project/session persistence, bounded research, exports and HTTPS.
6. If verification fails, use rollback below. Record SHA, downtime, tests and outcome.

## 5. Backup (consistent recovery point)

**Policy proposal:** daily recoverable state-disk snapshots, with **at least 14 retained daily points**, plus separate protected encrypted backup copies where configured. Scheduling/retention is not proof of recovery. Confirm approved retention and access policies before automation.

1. Notify active users and prevent new research; wait for or account for in-flight tasks.
2. Stop SIGMA with `sudo systemctl stop sigma.service` and verify application writers are stopped. Stop/disable any separate write workers as appropriate.
3. Confirm the exact `sigma-state` disk and mounted `/srv/sigma-state/auth` tree; preserve **together** user workspace trees, auth/subject mappings, session/outcome/artifacts and accounting SQLite databases.
4. Snapshot the disk from an authorized operator terminal, replacing `PROJECT_ID` only after confirmation:

```sh
gcloud compute disks snapshot sigma-state --project=PROJECT_ID \
  --zone=us-west1-b --snapshot-names="sigma-state-$(date -u +%Y%m%dT%H%M%SZ)"
```

5. If configured, create the separate encrypted archive in private Cloud Storage using the exact approved procedure in [Cloud Deployment](CLOUD_DEPLOYMENT.md#backup-restart-update-and-rollback). Check snapshot completion, restricted IAM and recovery-point metadata; never expose credentials or unencrypted backups.
6. Restart with `sudo systemctl start sigma.service` and verify health, disk mount and saved workspace access. Record recovery-point ID and timestamp.

**Do not** take a live snapshot of changing SQLite and workspace files and describe it as application-consistent.

## 6. Restore drill (non-production) / disaster recovery

1. Choose a named recovery-point snapshot; record original disk identity and SHA/version compatibility. **Never restore over the production disk as a first test.**
2. Create a **new separate disk** from that snapshot in the matching approved zone, mount only on an isolated recovery/test host or dedicated mount location, and verify its UUID/permissions.
3. Start a private compatible SIGMA stack (no public access and no outbound billable provider requests); verify SQLite integrity, Google identity mapping, two distinct user workspaces, saved research/session artifacts, TeX/PDF outputs and accounting ledger consistency.
4. Document any migration or version mismatch, restore duration, missing artifacts and confirmed recoverable timestamp. Clean up test resources only after evidence is retained.
5. For a production incident, explicitly authorize outage and cutover, stop writers, preserve the damaged disk for investigation, attach the *verified restored* disk, check UUID/fstab and permissions, preflight, start service, validate identity/isolation, then reopen traffic.
6. Declare any irrecoverable interval or uncertain in-flight provider calls; never silently reconstruct or zero spending reservations.

## 7. Rollback code (not data)

1. Preserve backups, current images and prior release SHA; stop service.
2. Restore the earlier compatible `SIGMA_RELEASE` and images **without deleting volumes**. Do not roll software back across an incompatible schema migration.
3. Run preflight and restart service; verify identities, saved projects, outstanding reservations and exports.
4. If data/schema are incompatible, pause rollout and follow the explicit restore/cutover procedure, with owner authorization. Record incident, evidence and outcome.

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
