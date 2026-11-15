#!/usr/bin/env bash
# Application-consistent GCE snapshot with guarded retention.
set -Eeuo pipefail
umask 077

readonly SERVICE=sigma.service
readonly MOUNT=/srv/sigma-state
readonly STATE_DIR=/var/lib/sigma-backup
readonly LOCK_FILE=/run/lock/sigma-state-backup.lock

log() { printf 'sigma-backup: %s\n' "$*"; }
fail() { log "FAIL: $*" >&2; exit 1; }

on_exit() {
  local status=${1:-$?}
  if (( status != 0 )); then
    install -d -m 0700 "$STATE_DIR"
    date -u +%FT%TZ > "$STATE_DIR/last-failure.tmp"
    mv -f "$STATE_DIR/last-failure.tmp" "$STATE_DIR/last-failure"
    log "FAIL: backup command exited ${status}; inspect journal with: journalctl -u sigma-backup.service"
  fi
  if [[ ${service_was_active:-0} == 1 ]]; then
    if ! systemctl start "$SERVICE"; then
      log "CRITICAL: backup ended with status ${status}; could not restart ${SERVICE}" >&2
      exit 1
    fi
    log "restarted ${SERVICE}"
  fi
}
trap 'backup_status=$?; on_exit "$backup_status"' EXIT
trap 'exit 143' TERM INT

[[ $EUID -eq 0 ]] || fail 'must run as root'
command -v gcloud >/dev/null || fail 'gcloud is unavailable'
command -v docker >/dev/null || fail 'Docker CLI is unavailable'
command -v flock >/dev/null || fail 'flock is unavailable'
: "${SIGMA_BACKUP_PROJECT:?set SIGMA_BACKUP_PROJECT in /etc/sigma/backup.env}"
: "${SIGMA_BACKUP_ZONE:?set SIGMA_BACKUP_ZONE in /etc/sigma/backup.env}"
: "${SIGMA_BACKUP_DISK:=sigma-state}"
: "${SIGMA_BACKUP_RETENTION:=14}"
[[ $SIGMA_BACKUP_DISK =~ ^[a-z][a-z0-9-]{0,62}$ ]] || fail 'invalid backup disk name'
[[ $SIGMA_BACKUP_RETENTION =~ ^[0-9]+$ ]] && (( SIGMA_BACKUP_RETENTION >= 14 )) || fail 'retention must be at least 14 snapshots'
[[ $(findmnt -n -o TARGET --target "$MOUNT" 2>/dev/null || true) == "$MOUNT" ]] || fail "$MOUNT is not a mounted filesystem"
[[ -d "$MOUNT/auth" && ! -L "$MOUNT/auth" ]] || fail 'auth state directory is missing or symlinked'
device_link="/dev/disk/by-id/google-${SIGMA_BACKUP_DISK}"
[[ -e $device_link ]] || fail "expected GCE disk device ${device_link} is unavailable"
expected_device=$(readlink -f "$device_link")
mounted_source=$(findmnt -n -o SOURCE --target "$MOUNT")
mounted_device=$(readlink -f "$mounted_source" 2>/dev/null || true)
if [[ $mounted_device != "$expected_device" ]]; then
  partition_parent=$(lsblk -ndo PKNAME "$mounted_device" 2>/dev/null || true)
  [[ -n $partition_parent && "/dev/$partition_parent" == "$expected_device" ]] || \
    fail "$MOUNT is not mounted from the configured ${SIGMA_BACKUP_DISK} device"
fi
install -d -m 0700 /run/lock "$STATE_DIR"
exec 9>"$LOCK_FILE"
flock -n 9 || fail 'another backup is already running'

service_was_active=0
if systemctl is-active --quiet "$SERVICE"; then
  service_was_active=1
fi
if (( service_was_active )); then
  log 'stopping sigma.service to quiesce SQLite, workspace, artifact, and accounting writes'
  systemctl stop "$SERVICE"
  if systemctl is-active --quiet "$SERVICE"; then fail 'sigma.service is still active after stop'; fi
fi
if systemctl is-active --quiet "$SERVICE"; then fail "$SERVICE remains active"; fi
if [[ -n $(docker ps --quiet --filter label=com.docker.compose.project=sigma) ]]; then
  fail 'SIGMA Compose containers are still running after service stop'
fi
sync -f "$MOUNT"

disk_name=$(gcloud compute disks describe "$SIGMA_BACKUP_DISK" \
  --project "$SIGMA_BACKUP_PROJECT" --zone "$SIGMA_BACKUP_ZONE" --format='value(name)')
[[ $disk_name == "$SIGMA_BACKUP_DISK" ]] || fail 'configured source disk was not found'
stamp=$(date -u +%Y%m%dt%H%M%Sz)
snapshot="sigma-state-${stamp}"
log "creating snapshot ${snapshot} from ${SIGMA_BACKUP_DISK}"
gcloud compute disks snapshot "$SIGMA_BACKUP_DISK" \
  --project "$SIGMA_BACKUP_PROJECT" --zone "$SIGMA_BACKUP_ZONE" \
  --snapshot-names "$snapshot" --labels=sigma-daily-backup=true,sigma-source-disk=sigma-state

# gcloud normally waits for completion; explicitly check READY before any pruning.
status=''
for _ in $(seq 1 60); do
  status=$(gcloud compute snapshots describe "$snapshot" --project "$SIGMA_BACKUP_PROJECT" --format='value(status)' 2>/dev/null || true)
  [[ $status == READY ]] && break
  [[ $status == FAILED ]] && fail "snapshot ${snapshot} failed"
  sleep 5
done
[[ $status == READY ]] || fail "snapshot ${snapshot} did not reach READY (status: ${status:-unknown})"
rm -f "$STATE_DIR/last-failure"
printf '%s %s\n' "$(date -u +%FT%TZ)" "$snapshot" > "$STATE_DIR/last-success.tmp"
mv -f "$STATE_DIR/last-success.tmp" "$STATE_DIR/last-success"
log "snapshot ${snapshot} is READY"

# Retention is scoped to snapshots created by this service. Never prune on a
# failed/incomplete new point, and preserve the newest configured number.
listing=$(mktemp)
trap 'backup_status=$?; rm -f "$listing"; on_exit "$backup_status"' EXIT
gcloud compute snapshots list --project "$SIGMA_BACKUP_PROJECT" \
  --filter='labels.sigma-daily-backup=true AND status=READY' \
  --format='json(name,creationTimestamp,labels,sourceDisk)' > "$listing"
python3 /usr/local/libexec/sigma/backup-retention.py "$listing" "$SIGMA_BACKUP_RETENTION" | while IFS= read -r old_snapshot; do
  [[ $old_snapshot =~ ^sigma-state-[0-9]{8}t[0-9]{6}z$ ]] || fail "refusing unexpected snapshot name: ${old_snapshot}"
  log "pruning expired managed snapshot ${old_snapshot}"
  gcloud compute snapshots delete "$old_snapshot" --project "$SIGMA_BACKUP_PROJECT" --quiet
done
log "PASS: recovery point ${snapshot} READY; retention target ${SIGMA_BACKUP_RETENTION}; service restoration is handled on exit"
