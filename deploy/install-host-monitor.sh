#!/usr/bin/env bash
# Install T136 checks independently from Red's host and application installer.
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo 'FAIL: run as root on the GCE host' >&2; exit 1; }
[[ -r /etc/sigma/backup.env ]] || { echo 'FAIL: configure owner-approved /etc/sigma/backup.env first' >&2; exit 1; }
repo=$(cd "$(dirname "$0")/.." && pwd)
install -d -o root -g root -m 0755 /usr/local/libexec/sigma /etc/systemd/system
install -o root -g root -m 0750 "$repo/deploy/host-monitor.py" /usr/local/libexec/sigma/host-monitor.py
install -o root -g root -m 0644 "$repo/deploy/systemd/sigma-monitor.service" /etc/systemd/system/sigma-monitor.service
install -o root -g root -m 0644 "$repo/deploy/systemd/sigma-monitor.timer" /etc/systemd/system/sigma-monitor.timer
install -o root -g root -m 0644 "$repo/deploy/systemd/sigma-monitor-failure.service" /etc/systemd/system/sigma-monitor-failure.service
install -d -o root -g root -m 0700 /var/lib/sigma-backup
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/sigma-monitor.service /etc/systemd/system/sigma-monitor.timer /etc/systemd/system/sigma-monitor-failure.service
systemctl enable --now sigma-monitor.timer
if systemctl start sigma-monitor.service; then
  echo 'PASS: monitoring timer installed and initial checks passed.'
else
  echo 'INSTALLED WITH FAILING INITIAL CHECKS: timer is enabled; inspect sigma-monitor.service journal and resolve every reported check.' >&2
fi
