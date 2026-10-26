# T128 — GCE host readiness and runtime security

**Readiness: BLOCKED for production activation.** This review used current
`main` at `8e8d979`. It made no SSH connection, provider call, installer run,
service start, reboot, or infrastructure change. The host details in the
assignment (project, VM, address, DNS, TLS, and current placeholder page) are
operator supplied and were not independently observed.

Existing repository records preserve earlier operator observations: IAP SSH
worked; the attached `sigma-state` filesystem had UUID
`28ef67cb-4da8-46e7-9a8b-dce0470153a5`; `/srv/sigma-state` was `root:root 700`;
and the UUID mount was reported present after a reboot on 2026-10-25. The saved
`findmnt` output only recorded `rw,relatime`, not the hardened mount flags now
required by preflight. These dated observations do not establish current mount
options, app ownership, sandbox denial, or production service recovery.

## Verified from repository and offline checks

- `sigma.service` requires and orders after `docker.service` and
  `sigma-sandbox.service`. `RequiresMountsFor=/srv/sigma-state` asks systemd
  to generate the mount requirement and ordering for the path. Startup runs
  `gce_preflight.py` before `start-gce.sh`; the startup script refuses an
  absent or symlinked mount and sets `/srv/sigma-state/auth` to backend
  UID/GID 10001, mode 0700. Compose maps only that `auth` directory into the
  backend's persistent storage path.
- The disk preparation code plans a UUID-backed ext4/XFS mount with `nodev`,
  `nosuid`, and `noexec`; preflight compares the mounted and fstab identities
  and checks the private state root. These are code properties, not proof of
  the current host mount or its owner/mode.
- Host Docker is intended for the application stack. A distinct
  `sigma-sandbox` account and rootless Docker service run research containers.
  Installer and preflight policy exclude that account from `docker` and `sudo`
  groups and require a private 0660 sandbox socket. The backend has access to
  that socket; generated research containers do not receive the socket or
  state mount. A compromised backend can submit work to the rootless daemon,
  so the host boundary depends on the daemon retaining only the
  `sigma-sandbox` user's host permissions.
- Research containers are configured with UID/GID 65532, no network, read-only
  root, no capabilities, `no-new-privileges`, bounded memory/CPU/PIDs/time,
  and temporary artifact storage. No state, secret, or daemon socket mount is
  included in the runner command. T171 added preflight enforcement for the
  production Compose service identity, resource/security controls, and the
  edge's published ports. These source checks do not establish live kernel,
  daemon, or container behavior.
- Production Compose currently defines its own Caddy edge and defaults to
  publishing host TCP 80 and 443 on `0.0.0.0`; its Caddyfile terminates HTTPS
  and routes to backend/frontend on the private Compose network. This
  conflicts with the assignment's report of an already-running host Caddy on
  the same ports. The two listeners cannot both bind those host ports. The
  deployment needs an explicit choice: keep the Compose Caddy edge and retire
  the host Caddy, or configure a reviewed loopback upstream and host-Caddy
  routing mode. The repository does not currently provide the latter mode.
  Do not activate the service until this is resolved and preflight agrees with
  the selected design.
- The current expected service is `sigma.service`, a systemd oneshot with
  `RemainAfterExit=yes`; it runs the preflight and guarded Compose startup.
  Compose orders the edge after healthy backend and frontend services. Required
  host inputs include a reviewed release at `/opt/sigma/current`, protected
  `/etc/sigma/deploy.env`, secret files, attached and mounted state disk,
  Python/Sage images built on the sandbox daemon, both daemon services, and
  passing preflight. Values and service state are not verified on the VM.

## Boundary and acceptance status

| Check | Result | Evidence limit |
| --- | --- | --- |
| Unit dependency and startup ordering | PASS by source inspection | Native systemd verification and active state pending on Ubuntu. |
| State mount and backend ownership policy | PASS by source inspection | Current UUID, mount flags, owners, and reboot persistence pending on VM. |
| Research sandbox host-resource policy | PASS by source inspection | Actual rootless daemon and Python/Sage probes pending on target. Rootless shares the host kernel and is not a VM boundary. |
| Compose runtime hardening and public port policy | PASS by source inspection/preflight tests | Merged target config and running container inspection pending. |
| Caddy integration with current host listener | BLOCKED | Existing host Caddy is operator-reported; Compose edge defaults to conflicting 80/443 binds. |
| Production readiness | BLOCKED | No current host preflight, deployed release SHA, live disk/daemon inspection, or application startup acceptance. |

The stale tests in `deployment_package.py`, `gce_host.py`, and `host_monitor.py`
were reconciled to assert `RequiresMountsFor=/srv/sigma-state` plus explicit
Docker/sandbox `Requires` and `After` directives. This reflects the current
unit contract and retains the intended ordering.

On the review workstation, `docker info` returned security options
`apparmor`, `seccomp,profile=builtin`, and `cgroupns` with no `rootless` entry;
`docker compose version` failed because the Compose plugin is unavailable, and
`systemd-analyze` is not installed. Therefore merged production Compose
rendering, local rootless runtime execution, and native unit verification were
not performed here.

## Pending read-only live checks

Run after the authorized operator has IAP access. Do not enable or start
`sigma.service` during these checks. Do not print environment values or secret
contents.

From an authorized operator shell:

```sh
gcloud compute instances describe sigma-gce-01 \
  --project=sigma-research-prod --zone=us-west1-b \
  --format='yaml(name,status,networkInterfaces,disks,tags,serviceAccounts)'
gcloud compute firewall-rules list --project=sigma-research-prod \
  --format='table(name,network,direction,allowed,sourceRanges,targetTags)'
dig +short sigma-research.duckdns.org A
curl --fail --silent --show-error --head https://sigma-research.duckdns.org/
```

Expected: running VM has the approved static address, persistent state disk,
least-privilege service account and web tag; effective ingress is public TCP
80/443 and IAP-only SSH; DNS resolves to `136.66.128.82`; HTTPS presents a
trusted certificate. Firewall list output must be interpreted with the VM's
network and target tags; a broad list alone is not proof of effective rules.

Connect read-only through IAP:

```sh
gcloud compute ssh sigma-gce-01 --project=sigma-research-prod \
  --zone=us-west1-b --tunnel-through-iap
```

Then run:

```sh
cat /etc/os-release
uname -m
sudo lsblk -o NAME,SIZE,TYPE,FSTYPE,UUID,MOUNTPOINTS
sudo findmnt --target /srv/sigma-state --output SOURCE,FSTYPE,UUID,OPTIONS
sudo findmnt --fstab --evaluate --target /srv/sigma-state --output SOURCE,FSTYPE,UUID,OPTIONS
sudo stat -c '%U:%G %a %n' /srv /srv/sigma-state /srv/sigma-state/auth
id sigma-sandbox
id -nG sigma-sandbox
sudo systemctl is-enabled docker.service sigma-sandbox.service
sudo systemctl is-active docker.service sigma-sandbox.service
sudo systemctl show sigma.service -p Requires -p After -p RequiresMountsFor -p ActiveState -p SubState
sudo systemd-analyze verify /etc/systemd/system/sigma.service /etc/systemd/system/sigma-sandbox.service
sudo systemctl status caddy.service --no-pager
sudo ss -ltnp '( sport = :80 or sport = :443 or sport = :8000 or sport = :8080 )'
sudo /usr/local/libexec/sigma/gce_preflight.py --repository /opt/sigma/current --json
sudo docker info --format '{{json .SecurityOptions}}'
uid=$(id -u sigma-sandbox)
sudo -u sigma-sandbox env XDG_RUNTIME_DIR="/run/user/$uid" \
  docker --host "unix:///run/user/$uid/docker.sock" info --format '{{json .SecurityOptions}}'
sudo stat -c '%U:%G %a %F' "/run/user/$uid/docker.sock"
```

Expected: Ubuntu 24.04 amd64; Docker and sandbox are enabled, but
`sigma.service` remains inactive/disabled until separately authorized; state
mount source UUID equals fstab UUID and approved disk inventory, type ext4/XFS,
options include `nodev,nosuid,noexec`;
state root `root:root 700`, auth `10001:10001 700`; sandbox account is in
neither `docker` nor `sudo`; Docker and sandbox are active; service dependency
properties include `/srv/sigma-state`; unit verification succeeds. Caddy's
listeners must be reconciled with the chosen Compose-edge or loopback-proxy
design. Preflight must exit 0 with every row PASS. System Docker must not
report rootless; sandbox Docker must report rootless; socket must be a Unix
socket owned by `sigma-sandbox:sigma-sandbox` mode 660.

If preflight passes and the Caddy design is resolved, inspect merged Compose
and any existing stack without starting or changing it:

```sh
cd /opt/sigma/current
sudo docker compose --project-name sigma --env-file /etc/sigma/deploy.env \
  -f deploy/compose.yaml -f deploy/compose.gce.yaml config --format json |
  python3 -c 'import json,sys; c=json.load(sys.stdin); print(json.dumps({n:{k:c["services"][n].get(k) for k in ("user","read_only","cap_drop","security_opt","pids_limit","mem_limit","cpus","tmpfs","ports","volumes")} for n in ("backend","frontend","edge")},indent=2))'
sudo docker ps --filter label=com.docker.compose.project=sigma --format '{{.Names}}'
sudo docker inspect --format '{{.Name}} user={{.Config.User}} readonly={{.HostConfig.ReadonlyRootfs}} cap_drop={{json .HostConfig.CapDrop}} security={{json .HostConfig.SecurityOpt}} memory={{.HostConfig.Memory}} nano_cpus={{.HostConfig.NanoCpus}} pids={{.HostConfig.PidsLimit}} ports={{json .NetworkSettings.Ports}} mounts={{json .Mounts}}' \
  $(sudo docker ps -q --filter label=com.docker.compose.project=sigma)
```

These commands inspect configured/running policy only. Empty container output
means there is no runtime observation. The application-path Python/Sage
isolation probe starts containers and writes disposable test state; it is not
a read-only check and remains a separate approved acceptance action. Service
activation, reboot recovery, OAuth, and provider-backed research are outside
this assignment and remain unverified.
