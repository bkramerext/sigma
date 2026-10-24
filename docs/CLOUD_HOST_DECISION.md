# T22 alpha hosting selection and provisioning decision

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
