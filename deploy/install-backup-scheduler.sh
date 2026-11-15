#!/usr/bin/env bash
# Install the daily snapshot timer after the GCE state disk and gcloud IAM are ready.
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo 'FAIL: run as root on the GCE host' >&2; exit 1; }
[[ -r /etc/sigma/backup.env ]] || { echo 'FAIL: create owner-approved /etc/sigma/backup.env first' >&2; exit 1; }
repo=$(cd "$(dirname "$0")/.." && pwd)
install -d -o root -g root -m 0755 /usr/local/libexec/sigma /etc/systemd/system
install -o root -g root -m 0750 "$repo/deploy/backup-state.sh" /usr/local/libexec/sigma/backup-state.sh
install -o root -g root -m 0755 "$repo/deploy/backup-retention.py" /usr/local/libexec/sigma/backup-retention.py
install -o root -g root -m 0644 "$repo/deploy/systemd/sigma-backup.service" /etc/systemd/system/sigma-backup.service
install -o root -g root -m 0644 "$repo/deploy/systemd/sigma-backup.timer" /etc/systemd/system/sigma-backup.timer
install -o root -g root -m 0644 "$repo/deploy/systemd/sigma-backup-failure.service" /etc/systemd/system/sigma-backup-failure.service
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/sigma-backup.service /etc/systemd/system/sigma-backup.timer /etc/systemd/system/sigma-backup-failure.service
systemctl enable --now sigma-backup.timer
systemctl list-timers sigma-backup.timer --no-pager
echo 'PASS: daily snapshot timer installed; runbook still requires owner-approved first backup and restore drill.'
