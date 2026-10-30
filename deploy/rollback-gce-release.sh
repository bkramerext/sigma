#!/usr/bin/env bash
# Restore a previously built application release without touching persistent data.
set -Eeuo pipefail
fail() { echo "FAIL: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || fail 'run as root on the GCE host'
[[ $# -eq 3 && $2 == --backup-verified && $3 == --schema-compatible ]] || \
  fail 'usage: rollback-gce-release.sh PREVIOUS_40_CHAR_SHA --backup-verified --schema-compatible'
target=$1
[[ $target =~ ^[0-9a-f]{40}$ ]] || fail 'previous release must be a full lowercase commit SHA'
env_file=/etc/sigma/deploy.env
[[ -f $env_file && ! -L $env_file ]] || fail 'deployment environment file is missing or unsafe'
[[ $(stat -c '%a:%U:%G' "$env_file") == 600:root:root ]] || fail 'deployment environment file must be root:root mode 0600'
[[ $(findmnt -n -o TARGET --target /srv/sigma-state 2>/dev/null || true) == /srv/sigma-state ]] || fail 'state disk is not mounted; rollback refused'
if systemctl is-active --quiet sigma-backup.service; then fail 'state backup is active; wait for it to finish'; fi
current=$(sed -n 's/^SIGMA_RELEASE=\([0-9a-f]\{40\}\)$/\1/p' "$env_file")
[[ $current =~ ^[0-9a-f]{40}$ ]] || fail 'current SIGMA_RELEASE is missing or invalid'
[[ $current != "$target" ]] || fail 'requested rollback release is already active'
docker image inspect "sigma-backend:$target" >/dev/null 2>&1 || fail 'previous backend image is not present locally'
docker image inspect "sigma-frontend:$target" >/dev/null 2>&1 || fail 'previous frontend image is not present locally'

release_dir=/var/lib/sigma/releases
install -d -o root -g root -m 0700 "$release_dir"
backup="$release_dir/deploy.env.$current"
if [[ -e $backup ]]; then
  cmp -s "$backup" "$env_file" || fail "saved environment differs from current release configuration: $backup"
else
  install -o root -g root -m 0600 "$env_file" "$backup"
fi
temporary=$(mktemp /etc/sigma/deploy.env.XXXXXX)
rollback_active=0
restore_previous_env() {
  local restore_temp
  restore_temp=$(mktemp /etc/sigma/deploy.env.restore.XXXXXX)
  install -o root -g root -m 0600 "$backup" "$restore_temp"
  mv -f "$restore_temp" "$env_file"
}
cleanup() {
  rm -f "$temporary"
  if (( rollback_active )); then
    rollback_active=0
    if restore_previous_env; then
      systemctl restart sigma.service || logger -p daemon.crit -t sigma-rollback 'interrupted rollback restored prior environment but service restart failed'
    else
      logger -p daemon.crit -t sigma-rollback 'interrupted rollback could not restore prior environment; operator intervention required'
    fi
  fi
}
trap cleanup EXIT
python3 - "$env_file" "$temporary" "$target" <<'PY'
import os, re, sys
source, temporary, target = sys.argv[1:]
with open(source, encoding="utf-8") as stream:
    lines = stream.readlines()
matches = [i for i, line in enumerate(lines) if line.startswith("SIGMA_RELEASE=")]
if len(matches) != 1 or not re.fullmatch(r"[0-9a-f]{40}", lines[matches[0]].strip().partition("=")[2]):
    raise SystemExit("FAIL: expected exactly one valid SIGMA_RELEASE setting")
lines[matches[0]] = f"SIGMA_RELEASE={target}\n"
fd = os.open(temporary, os.O_WRONLY | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as stream:
    stream.writelines(lines)
    stream.flush()
    os.fsync(stream.fileno())
PY
chown root:root "$temporary"
chmod 0600 "$temporary"
mv -f "$temporary" "$env_file"
rollback_active=1
if ! /usr/local/libexec/sigma/gce_preflight.py --json --repository /opt/sigma/current; then
  restore_previous_env
  rollback_active=0
  fail 'preflight rejected rollback candidate; original release pin restored'
fi

if ! systemctl restart sigma.service; then
  restore_previous_env
  rollback_active=0
  systemctl restart sigma.service || logger -p daemon.crit -t sigma-rollback 'candidate failed and prior release restart failed; operator intervention required'
  fail 'rollback candidate failed to start; prior release pin restored'
fi
compose=(docker compose --project-name sigma --env-file "$env_file" -f /opt/sigma/current/deploy/compose.yaml -f /opt/sigma/current/deploy/compose.gce.yaml)
for attempt in $(seq 1 24); do
  backend=$("${compose[@]}" ps -q backend)
  frontend=$("${compose[@]}" ps -q frontend)
  edge=$("${compose[@]}" ps -q edge)
  if [[ -n $backend && -n $frontend && -n $edge ]] && \
     [[ $(docker inspect -f '{{.State.Health.Status}}' "$backend" 2>/dev/null || true) == healthy ]] && \
     [[ $(docker inspect -f '{{.State.Health.Status}}' "$frontend" 2>/dev/null || true) == healthy ]] && \
     [[ $(docker inspect -f '{{.State.Status}}' "$edge" 2>/dev/null || true) == running ]]; then
    rollback_active=0
    logger -t sigma-rollback "code rollback from ${current} to ${target} started and container healthchecks passed"
    echo "PASS: release pin switched from $current to $target; container healthchecks passed. Verify public HTTPS and application state per runbook."
    exit 0
  fi
  sleep 5
done
restore_previous_env
rollback_active=0
if ! systemctl restart sigma.service; then
  logger -p daemon.crit -t sigma-rollback 'container health check failed and prior release did not restart; operator intervention required'
fi
fail 'candidate container health checks failed; prior release pin restored and restart attempted'
