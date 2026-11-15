# T128 — Live GCE host readiness verification

**Assessment: BLOCKED for production start.** This attempt used current `main`
(`a335f3f` at inspection start) and the T171 checklist. It obtained no
connection to `sigma-gce-01`; consequently none of the requested host, runtime,
firewall, or preflight properties can be reported as a live PASS or FAIL.
Repository configuration and T171's offline checks are not substitutes for
host evidence. No installer, infrastructure mutation, service start, reboot,
production credential access, or state-changing test was performed.

## Access evidence

- `command -v gcloud` returned no executable.
- No GCE/Google Cloud connector is available in this session.
- `ssh -G sigma-gce-01` resolved to host `sigma-gce-01`, port 22, user `admin`,
  with no ProxyCommand.
- `getent ahostsv4 sigma-gce-01` returned no address.
- `ssh -o BatchMode=yes -o ConnectTimeout=8 sigma-gce-01 true` exited 255:
  `Could not resolve hostname sigma-gce-01`.
- No host preflight or host command ran. No live evidence was available to
  confirm VM identity, Ubuntu release, architecture, external IP, mounted state
  disk, daemon state, installed units, containers, or effective firewall rules.

## Readiness disposition

| Requirement | Result | Evidence / reason |
| --- | --- | --- |
| VM identity, Ubuntu, architecture, external IP | **BLOCKED** | VM name does not resolve; no GCE API access. |
| Persistent disk UUID, mount/options, owner/mode | **BLOCKED** | No SSH; current source/fstab UUID and directory permissions were not observed. |
| Rootless Docker, socket permissions, isolation | **BLOCKED** | No daemon info/socket or application-path isolation run. |
| Systemd dependencies/startup configuration | **BLOCKED** | No installed unit state or systemd manager verification on target. |
| Container resource/security policy | **BLOCKED** | T171 verifies source/preflight policy offline only; no live Compose config or container inspection. |
| GCE firewall: 80/443 and IAP SSH | **BLOCKED** | No GCE API access; effective ingress rules and external exposure unknown. |
| Host preflight | **BLOCKED / NOT RUN** | `/usr/local/libexec/sigma/gce_preflight.py` was not run on the host. |
| Startup/recovery gate | **BLOCKED** | Do not start `sigma.service`; no readiness rows are confirmed PASS. A separately approved reboot recovery observation remains required before inviting users per T171. |

No new security/configuration defect was observable without target access. The
external IP and firewall exposure are **unknown**, not assumed safe. T171's
residual rootless shared-kernel risk and installer partial-state behavior
remain relevant. This assignment did not duplicate the coordinator's mount
assertion corrections.

## Access prerequisites

An operator must make the existing VM reachable through the approved IAP path
and provide this session a usable, least-privilege GCE read role plus IAP/OS
Login SSH authorization, without sharing production credentials in chat. The
host must be `sigma-gce-01` in project `sigma-research-prod`, zone `us-west1-b`,
or the operator must supply the corrected identifiers. `gcloud` and its
approved noninteractive authentication path must then be available, or an
approved SSH alias must include the IAP tunnel. No software installation is
part of this assignment.

## Exact next read-only checks

First obtain identity and IP from GCE metadata/API:

```sh
gcloud compute instances describe sigma-gce-01 \
  --project=sigma-research-prod --zone=us-west1-b \
  --format='yaml(name,status,machineType,networkInterfaces[].network,networkInterfaces[].networkIP,networkInterfaces[].accessConfigs[].natIP,tags.items)'
gcloud compute ssh sigma-gce-01 \
  --project=sigma-research-prod --zone=us-west1-b --tunnel-through-iap
```

In the SSH session, run the identity, disk, services, systemd verification,
preflight, daemon, and container-policy/runtime commands in
[`T171_HOST_READINESS.md`](T171_HOST_READINESS.md), sections 1–3. Capture
sanitized stdout, exit statuses, host release SHA, and timestamps. In
particular, preflight must exit 0 with every status PASS; the state mount UUID
must match fstab and have `nodev,nosuid,noexec`; the expected rootless socket
must be owned by `sigma-sandbox:sigma-sandbox` mode 660; and actual container
inspect must agree with the reviewed config. The packaged
`python -m sigma.cloud_runtime_check` is listed in T171 as an application-path
isolation proof, but it executes jobs and writes a disposable project. It was
not run here because this assignment prohibits state-changing tests; arrange a
separately scoped, approved runtime acceptance exercise after the read-only
checks pass.

Inspect GCE ingress policy using the instance's actual network, network tags,
and service account from the instance description. Enumerate all ingress rules
on that network, then evaluate enabled rules that target the instance by tag or
service account and include applicable source ranges/protocols/ports. Confirm
that public ingress is limited to TCP 80/443 and SSH is limited to IAP TCP 22
from `35.235.240.0/20`; confirm TCP 8000, 5173, 2375 and 2376 are not exposed.
The read-only starting query is:

```sh
gcloud compute firewall-rules list --project=sigma-research-prod \
  --filter='direction=INGRESS' \
  --format='table(name,network,disabled,sourceRanges,allowed,targetTags,targetServiceAccounts)'
```

A raw rule list is not by itself proof of effective exposure: reconcile every
rule against the VM's network, tags, service account, source range, protocol,
and port. Do not change rules under this assignment.

## Actions before first start

1. Restore approved read-only GCE/IAP access and rerun this verification.
2. Resolve every BLOCKED item above with target evidence; any preflight nonzero,
   FAIL/BLOCKED row, mount mismatch, socket mismatch, unexpected published
   port, or unexpected firewall ingress remains a launch blocker.
3. Establish that production env/secret metadata is present without printing
   values. Do not expose secrets in the handoff.
4. Only after all pre-start checks pass, have the authorized operator separately
   approve and perform the documented `systemctl enable --now sigma.service`
   start, then verify Compose health and the private auth status route.
5. Before inviting users, schedule and separately authorize the T171 reboot
   recovery exercise; verify disk UUID, workspace persistence, daemon/socket,
   containers and preflight after reboot.

Repository test results and elapsed time belong in the active ticket or a
committed PR handoff under `messages/`.
