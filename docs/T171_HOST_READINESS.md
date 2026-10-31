# T171 — GCE host and SIGMA runtime readiness

**Assessment: BLOCKED for production start.** The repository package is ready
for a controlled host verification, but the actual Ubuntu host's current
preflight, systemd units, rootless daemon, mounted disk, deployed containers,
and reboot recovery have not all been observed. T128 explicitly requires real
host evidence. This audit made no provider calls, installer invocation, VM
change, service start, or reboot.

## Evidence and disposition

| Area | Offline evidence | Assessment |
| --- | --- | --- |
| Rootless Docker separation | T128 installs a dedicated `sigma-sandbox` user and user daemon; preflight checks rootless security option, socket ownership/mode, user groups, and that the system Compose daemon is not rootless. `tests/gce_host.py` tests the policy. | **BLOCKED** — no live `docker info`, socket, account, or adversarial runner observation on target. A rootless daemon is a useful boundary, not a kernel-isolation guarantee. |
| State disk and access boundary | `prepare_state_disk.py` plans UUID fstab entries with `nodev,nosuid,noexec`; preflight compares mounted and fstab UUID/type/options and requires a private root. Startup refuses symlinks/unmounted disk; backend owns only `auth` mode 0700. | **PARTIAL PASS / BLOCKED** — code and T127's recorded reboot mount observation exist, but the current mount identity, fstab, ownership, and sandbox denial need rereading on target. No boot-disk fallback is accepted. |
| Systemd ordering and recovery | `sigma.service` has `RequiresMountsFor=/srv/sigma-state`, requires/after-orders Docker and rootless daemon, runs preflight before guarded startup, and uses restart policy. Compose waits for healthy backend/frontend before Caddy. | **PASS by inspection / BLOCKED live** — unit parser/manager behavior and actual enabled/active state have not been checked on the target. The three old assertions in `deployment_package.py`, `gce_host.py`, and `host_monitor.py` still expect explicit mount-unit dependencies; they were intentionally not changed. |
| Container limits/restrictions | Production Compose defines app UIDs, read-only roots, dropped capabilities, `no-new-privileges`, PID/memory/CPU bounds, restricted tmpfs, and only edge TCP 80/443 publication. Research runners use no network, 512 MiB Python / 1 GiB Sage, one CPU, 64 PIDs, read-only root, non-root UID, no capabilities, and 15/60 second timeouts. | **PASS by config inspection; gap fixed** — preflight previously did not validate most Compose resource/security values. It now rejects a missing reviewed policy or unexpected published port. Actual container inspect and runner execution remain unverified. |
| Host readiness and reboot recovery | Read-only preflight checks env/secret metadata, mount identity, daemons, images, Compose, systemd unit and runtime. Host monitor timer runs after boot and periodically. | **BLOCKED** — preflight cannot be run against the actual host under this assignment, and no current reboot recovery observation exists for the installed service/runtime. |
| Installer safety/failure handling | Installer gates on Ubuntu 24.04 amd64 and root before package changes, pins Docker packages, creates a non-privileged sandbox account, checks subordinate IDs, installs units, and fails if rootless daemon readiness is absent. `set -Eeuo pipefail`; host guard is separately tested without invoking installer. | **PASS by inspection / BLOCKED live** — no installation simulation or live installer run was performed. Failure is fail-fast but not transactional; partial package/user/unit changes may remain and require inspection before retry. |

### Launch blockers and risks

1. Do not start `sigma.service` until target-host preflight exits 0 and every
   row is PASS. No current T128 production preflight result is supplied.
2. Confirm the persistent UUID-backed disk is mounted at `/srv/sigma-state`
   before startup; missing/incorrect disk must fail closed. T127's recorded
   reboot mount result is not evidence of T128 application recovery.
3. Verify the actual rootless daemon and actual running container host config;
   Compose source/config inspection alone does not prove host isolation.
4. Verify installed/enabled service state and one approved reboot recovery
   exercise before inviting users. This is intentionally deferred here.
5. Container rootless isolation shares the host kernel. A host/kernel/runtime
   escape remains a residual risk; do not expose the daemon socket or assume
   rootless means equivalent to a VM boundary.
6. Installer errors can leave idempotent but partial state. Do not blindly
   rerun after a failure; first inspect package, user/group, subordinate ID,
   systemd, socket and disk state.
7. Disk-loss recovery, backup restore, capacity, availability and public hosted
   identity/research acceptance are separate gates, not established by T171.
8. The deployed GCE firewall rules and external address were not inspected in
   this offline audit. Before public launch confirm ingress is limited to TCP
   80/443 and IAP SSH only; 8000, 5173, 2375 and 2376 must remain closed.

## Offline regression change

`deploy/gce_preflight.py` now checks that the merged production Compose has the
reviewed backend/frontend/edge read-only, UID, capabilities, privilege,
resource and tmpfs controls, and that only edge publishes TCP 80/443. The
focused regression rejects a removed PID limit and an unexpected 8000 port.
This narrows the previous false-PASS risk; it does not inspect live container
configuration.

## Later live-host verification

Run only after separate operator authorization and when the target VM is
available. These commands are read-only except the explicitly identified
reboot exercise. Do not paste secrets or full container environment output.

### 1. Identity, disk and host services (read-only)

```sh
gcloud compute ssh sigma-gce-01 --project=sigma-research-prod --zone=us-west1-b --tunnel-through-iap
```

Expected: IAP SSH connects to the approved VM. In that shell:

```sh
cat /etc/os-release
uname -m
lsblk -o NAME,SIZE,TYPE,FSTYPE,UUID,MOUNTPOINTS
sudo findmnt --target /srv/sigma-state --output SOURCE,FSTYPE,UUID,OPTIONS
sudo findmnt --fstab --evaluate --target /srv/sigma-state --output SOURCE,FSTYPE,UUID,OPTIONS
sudo stat -c '%U:%G %a %n' /srv/sigma-state /srv/sigma-state/auth
sudo systemctl is-enabled docker.service sigma-sandbox.service sigma.service
sudo systemctl is-active docker.service sigma-sandbox.service
sudo systemctl show sigma.service -p Requires -p After -p RequiresMountsFor -p ActiveState -p SubState
sudo systemd-analyze verify /etc/systemd/system/sigma.service /etc/systemd/system/sigma-sandbox.service
```

Expected: Ubuntu `24.04`, `x86_64`; mount source UUID exactly matches fstab,
type `ext4` or `xfs`, options include `nodev,nosuid,noexec`; `/srv/sigma-state`
is `root:root 700`, `auth` is `10001:10001 700`; services enabled as intended,
Docker and sandbox active; systemd shows mount requirement and valid units.
Never run `mkfs` during verification.

### 2. Preflight and daemons (read-only)

```sh
sudo /usr/local/libexec/sigma/gce_preflight.py --repository /opt/sigma/current --json
sudo docker info --format '{{json .SecurityOptions}}'
uid=$(id -u sigma-sandbox)
sudo -u sigma-sandbox env XDG_RUNTIME_DIR="/run/user/$uid" docker --host "unix:///run/user/$uid/docker.sock" info --format '{{json .SecurityOptions}}'
sudo stat -c '%U:%G %a %F' "/run/user/$uid/docker.sock"
```

Expected: preflight exits **0** and every status is `PASS`; system Docker is
not rootless; dedicated daemon reports `rootless`; socket is a Unix socket
owned by `sigma-sandbox:sigma-sandbox` mode `660`. Any `FAIL`, `BLOCKED`, nonzero exit or
secret-bearing output blocks launch.

### 3. Runtime container policy (read-only)

```sh
sudo docker compose --project-name sigma --env-file /etc/sigma/deploy.env \
  -f /opt/sigma/current/deploy/compose.yaml \
  -f /opt/sigma/current/deploy/compose.gce.yaml config --format json |
  python3 -c 'import json,sys; c=json.load(sys.stdin); print(json.dumps({n:{k:c["services"][n].get(k) for k in ("user","read_only","cap_drop","security_opt","pids_limit","mem_limit","cpus","tmpfs","ports")} for n in ("backend","frontend","edge")},indent=2))'
sudo docker ps --filter label=com.docker.compose.project=sigma --format '{{.Names}}'
sudo docker inspect --format '{{.Name}} user={{.Config.User}} readonly={{.HostConfig.ReadonlyRootfs}} cap_drop={{json .HostConfig.CapDrop}} security={{json .HostConfig.SecurityOpt}} memory={{.HostConfig.Memory}} nano_cpus={{.HostConfig.NanoCpus}} pids={{.HostConfig.PidsLimit}} ports={{json .NetworkSettings.Ports}}' \
  $(sudo docker ps -q --filter label=com.docker.compose.project=sigma)
```

Expected config and inspect agree: backend `10001:10001`, RO, cap drop ALL,
no-new-privileges, 5 GiB / 2 CPUs / 256 PIDs; frontend `101:101`, RO, cap drop
ALL, no-new-privileges, 128 MiB / 64 PIDs; edge RO, cap drop ALL plus only
`NET_BIND_SERVICE`, no-new-privileges, 256 MiB / 128 PIDs; only edge publishes
TCP 80/443. Empty output from inspect means the stack is not running and does
not count as acceptance. Check mount destinations separately without printing
container environment values.

Research execution must also be exercised through the existing application
path with an approved isolated test identity: execute one harmless Python and
one Sage probe; expect completion, bounded output, no network access, no host
or state-disk reads, and no daemon socket in the runner. Save only sanitized
status/output evidence. For the packaged isolation/Python/Sage/PDF smoke proof,
use the documented command after the application stack and both rootless images
are ready:

```sh
cd /opt/sigma/current
sudo docker compose --env-file /etc/sigma/deploy.env \
  -f deploy/compose.yaml -f deploy/compose.gce.yaml \
  exec -T backend python -m sigma.cloud_runtime_check
```

Expected JSON reports `daemon_rootless: true`; Python and Sage each report
`host_secret`, `network`, `host_state`, and `docker_socket` as `blocked`, with
UID `65532`; PDF has a valid `%PDF-` header and snapshot/PDF integrity passes.
This writes only a disposable project inside the backend container's `/tmp`
and runs actual generated code in runner containers. Do not use `docker run`
against the production daemon as a substitute for the application path.

### 4. Startup and reboot recovery

After all preflight and runtime checks pass and an operator authorizes the
start, use the documented `sudo systemctl enable --now sigma.service`; expect
active `exited` oneshot state with the Compose services healthy and preflight
still PASS. Verify `/api/cloud-auth/status` through the private/approved route
and check service logs for errors without dumping environment values.

Reboot is **not authorized by this assignment**. For a separately approved
maintenance window, record active service, mounted source UUID, release SHA,
and a known test workspace; reboot once; then repeat sections 1–3 and confirm
the same disk UUID and workspace, daemon/socket and Compose health, service
recovery, and no preflight failures. A successful boot alone is not a recovery
pass.

## Offline test results

Record actual commands and results in the active ticket or a committed PR
handoff under `messages/`. No live host commands, installer, reboot, provider
calls or infrastructure changes were run for this readiness note.
