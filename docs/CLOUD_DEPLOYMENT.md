# SIGMA Cloud Deployment

**Current state (2026-10-29):** SIGMA v0.1.4 is deployed on the GCE host
listed below. Public anonymous checks and production container health passed.
Authenticated hosted acceptance is partial: no Google account was authenticated
and no production research session was started. See [Status](STATUS.md) for the
latest evidence. This document describes the observed deployment and links to
operator procedures; it does not authorize infrastructure, billing, credential,
production-setting, or provider changes.

Use [Operations Runbook](OPERATION_RUNBOOK.md) for commands that operate on the
host. Historical planning notes are retained at the end of this document and
are not current deployment instructions. Do not copy commands from an old
proposal into the production project.

## Observed deployment

| Resource | Current record | Evidence / limit |
| --- | --- | --- |
| Infrastructure project | `sigma-research-prod` (`SIGMA Production`), project number `224387813390` | Operator-reported; detailed IAM and billing posture have not been independently audited. |
| OAuth project | `sigma-auth-512601` (`SIGMA Auth`), project number `665111821572` | Operator-reported from Cloud Console. |
| VM | `sigma-gce-01`, Ubuntu 24.04 amd64, `e2-standard-2`, `us-west1-b` | Running; IAP/OS Login observed. Worker IAM is broader than least privilege. |
| State disk | `sigma-state`, 30 GB `pd-balanced`, `us-west1-b` | Mounted at `/srv/sigma-state`; UUID-backed mount survived reboot. Never format this existing disk. |
| Public address and DNS | `136.66.128.82`; `sigma-research.duckdns.org` | DNS, public HTTPS and API probe passed. Public TCP 80/443 terminate at host Caddy; SSH is IAP-only. |
| Runtime identity | `sigma-runtime` service account | Attached and used. Its full effective IAM grants have not been independently audited. |
| Deployed release | `6fa626bdfc1f07cb873103dfed2323864d4fb280` (v0.1.4) | Read-only GCE inspection on 2026-10-29 confirmed configured release and backend/frontend image labels match; all three containers healthy. This differs from the previously recorded `2761c0e12190807bafabe58445d6beac479140c4`; reconcile release-record/history provenance before cutover. |
| Recovery | One-off READY snapshot `sigma-state-v014-20261029-0606` before v0.1.4 | Read-only GCE inspection on 2026-10-29 confirmed READY and `sigma-state` source. A restore drill of this exact snapshot was not done. The daily backup timer and `/etc/sigma/backup.env` are absent. An earlier snapshot clone passed the offline restore verifier; see Status and Runbook. |
| Billing and current spend | Unknown | Prior console screenshots and estimates are historical observations, not current billing evidence. Budget alerts do not cap charges. OpenAI billing is separate from GCP. |

The production endpoint reported hosted auth ready with `mock_auth=false`;
unauthenticated project and research-session requests returned 401. Anonymous
Chrome loaded Home, Google sign-in, and the guest welcome. These observations do
not establish successful OAuth, access control across real identities,
workspace isolation, invitation mail delivery, sponsored inference, or the
research workflow. The About view displayed v0.1.4 but reported build SHA
`unknown`; the host checkout and image labels independently establish the
source SHA.

## Runtime and security boundaries

The deployment uses the Python FastAPI backend and static frontend built from
locked dependencies, with Compose and Caddy. On GCE, host Caddy terminates TLS
and forwards to the Compose edge at loopback TCP 18080. Backend and frontend
ports are not host-published. The public endpoint probe verifies HTTPS,
redirects, a deep link, auth status, and that application/daemon ports are
unreachable; it does not verify authenticated behavior.

Private auth databases, subject/workspace mappings, projects, research records,
artifacts, and cloud spending reservations are stored under the mounted state
disk. The app uses a separate rootless Docker daemon for Python/Sage execution;
the host rootful Docker socket must not be mounted into the app. Host preflight
and Compose health checks verify configuration and process readiness, but do
not replace the target-host runner isolation test or identity-based acceptance.

Hosted Google sign-in identifies a SIGMA account; it does not provide an
inference credential. The hosted deployment selects a separately configured
provider route and sponsorship policy. Personal ChatGPT/API credentials are
not forwarded to hosted inference. API usage can incur charges outside GCP.
Provider calls with uncertain outcomes retain their spending reservations and
must not be replayed or removed from the ledger to make balances appear clean.

The app's health checks and local packaged deployment checks do not prove
availability targets, capacity, backup recoverability, or production data
isolation. No service-level objective or tested RTO/RPO is established.

## Administrator contact and subject binding

`SIGMA_CLOUD_ADMIN_CONTACT_EMAIL` is configuration for the public invitation
contact and, on a fresh auth database, the initial administrator email. On the
first successful Google OIDC sign-in whose verified email matches the
configured address, SIGMA stores that email's stable Google subject in the auth
database and grants that identity administrator privileges. This is not a
first-visitor-wins rule: another verified email cannot claim initial admin.

The original bootstrap email/subject binding persists in the auth database.
Changing the environment variable does not migrate or revoke that original
administrator. The newly configured contact can also become an administrator
when its verified Google identity first signs in; that contact email is then
pinned to its subject in the same persistent database. If the configured
contact changes again, the original bootstrap administrator remains; implicit
administrator status follows the currently configured contact, while prior
non-bootstrap contact bindings remain stored but are not automatically active
as the current contact. Existing admin grants and identities must be reviewed
before changing contact configuration.

The retired `SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL` variable is unsupported and
must be removed from deployment configuration. Preflight rejects it. It does
not override or alias the current contact variable. Preserve the existing auth
state directory during a contact change; do not edit or delete the database to
transfer administrator access. The deployment template and code tests cover
first binding, contact changes, stored subject binding, admin role, and retired
variable rejection.

For OAuth origin, callback, cookies, access grants/revocation, and local Google
testing details, use the current code and [Getting Started](GETTING_STARTED.md).
Never place OAuth secrets, API keys, or SMTP passwords in this document or in
Git. The deployment uses protected secret files; secret presence checks do not
validate that credentials work. Production OAuth and invitation delivery have
not been validated by this release acceptance.

## Operational procedures

Follow the [Operations Runbook](OPERATION_RUNBOOK.md), which is the executable
source for the current host:

- Read-only diagnosis, preflight, health, DNS, TLS, and public endpoint checks:
  [routine health](OPERATION_RUNBOOK.md#2-routine-health-and-diagnosis).
- Service restart and VM reboot checks:
  [restart and recovery](OPERATION_RUNBOOK.md#3-restart-service--recover-after-vm-reboot).
- Exact-SHA update and pre-cutover recovery point:
  [application release](OPERATION_RUNBOOK.md#4-application-release--update).
- Daily snapshot procedure and prerequisites:
  [daily backup](OPERATION_RUNBOOK.md#5-daily-state-disk-backup).
- Separate-disk restore verification:
  [restore drill](OPERATION_RUNBOOK.md#6-restore-drill-non-production--disaster-recovery).
- Code rollback, which does not roll back data:
  [rollback](OPERATION_RUNBOOK.md#7-rollback-code-not-data).

Current production has a one-off pre-release snapshot but no configured daily
backup timer or approved backup environment file. Do not describe recurring
backups as enabled. A snapshot is not proof of recoverability. A code rollback
keeps current persistent data; it does not reverse schema/data changes. The
runbook requires an operator-confirmed recovery point and schema compatibility
before rollback. If a data restore is necessary, use a separate recovery disk
and the verifier; never overwrite the production state disk as an ad hoc
rollback.

Provisioning commands in the retained historical material below are not
applicable to the existing VM. Never rerun resource creation, firewall, disk
formatting, or installer steps on the current project as a way to deploy an
application release. A release uses the guarded exact-SHA host workflow in the
runbook. Cloud changes, billing changes, public ingress, production settings,
OAuth credentials, and provider-backed checks require explicit operator
authorization.

## Earlier sizing and cost decisions

The initial readiness estimate (2026-10-23) modeled an always-on
`e2-standard-4`, 100 GiB standard boot disk, and 200 GiB balanced state disk,
with modeled monthly/90-day totals of $125.49/$371.31 before launch and
$132.57/$392.34 including illustrative backups and traffic. These were
planning figures, not invoices or current quotes. The operator later selected
an `e2-standard-2` VM and 30 GB state disk. The old totals do not describe the
actual resource set or current spend and must not be used for budget approval.

A $300 trial balance and a budget alert were reported in October 2026, but
current trial eligibility, expiration, project association, available credit,
alert delivery, and spending are unverified here. Alerts are notifications,
not hard spend caps; trial terms may stop resources. Recalculate using current
GCP rates and observed usage before making a spending decision. OpenAI API
charges are separate. A $0 or bounded SIGMA allowance does not constrain the
provider's billing account by itself.

The original decisions retained for context are: use GCE for a temporary
invited alpha; use DuckDNS rather than a GCP-managed zone; attach a separate
persistent state disk; keep SSH on IAP; and reduce initial VM/disk sizing for
cost control. The duplicate project `sigma-production-512718` was reported
shut down and should not be used. Detailed proposals and feasibility notes
below are historical context only; current IDs and observed outcomes are in
the inventory above and runbook.

## Acceptance still incomplete

As of the v0.1.4 status record, the following have not been validated on the
live deployment: Google sign-in with an authorized identity; denied/revoked
identity behavior; administrator operations; invitation email delivery;
identity-based project/session loading; workspace isolation across real
accounts; authenticated project and research controls; provider-backed
research; routine backup scheduling and retention; restore of the exact
pre-v0.1.4 snapshot; fresh post-deploy reboot acceptance; full runner isolation
on the target host; externally delivered operational alerts; and rollback
against the deployed persistent data. No clean-machine OAuth or live paid
inference test is claimed.

The current evidence and owners' remaining acceptance matrix are maintained in
[Status](STATUS.md) and the [Operations Runbook](OPERATION_RUNBOOK.md). GitHub
Issues and PRs remain the authoritative development history; this guide is not
a ticket tracker.

---

# Historical hosting and external-host notes

The material below records earlier architecture exploration and deployment
planning. It predates production deployment and may contain obsolete
assumptions, proposed resource names, sizes, prices, or acceptance states. It
is retained for decision history only. It is not an executable procedure or
current evidence. Use the observed inventory and Operations Runbook above for
production.

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

Make SIGMA accessible to a small number of outside users as a **genuine, interactive, polished research showcase**, while retaining a useful locally running application. The intended audience includes people evaluating the product and engineering approach. This is not a plan to launch a production SaaS business.

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

## T128 host-readiness gate (coordinator integration)

Before T129's first application start, run the read-only host checks documented in [T128_HOST_READINESS.md](T128_HOST_READINESS.md). This gate does not require production `deploy.env`, OAuth, or provider secrets. Run `--host-readiness` before initial deployment and `--after-reboot` after an authorized reboot. Capture sanitized output and distinguish PASS, FAIL, and BLOCKED. Live disk identity/mount options, rootless Docker, installed systemd configuration, effective GCE firewall exposure, and runtime isolation must be observed on the target VM; source-level tests do not substitute for those checks. The latest operator access limitation is recorded in [T128_LIVE_READINESS.md](T128_LIVE_READINESS.md).

## Explicit ChatGPT sponsor provisioning (#200)

Hosted model discovery permits authenticated read-only checks; hosted personal
OAuth and account mutation routes remain blocked. To use the designated sponsor
`zetacontinuation@gmail.com`, explicitly configure ChatGPT mode and provision its
protected SIWC session on the VM. Google sign-in alone cannot create that grant.
See [Sponsor connection and provisioning](T200_SPONSOR_CONNECTION.md) for the
settings, private import procedure, refresh ownership, and acceptance boundary.
API-key mode remains the compatibility default; ChatGPT mode never falls back
to it. Existing user/global admission and budget guards apply in both modes.
