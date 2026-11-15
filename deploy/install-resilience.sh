#!/usr/bin/env bash
# Install production watchdog and log expiry; does not restart the application.
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo "Must run as root" >&2; exit 1; }
repo=$(cd "$(dirname "$0")/.." && pwd)
mountpoint -q /srv/sigma-state || { echo "State disk not mounted" >&2; exit 1; }
[[ ! -L /srv/sigma-state/auth ]] || { echo "Unsafe state path" >&2; exit 1; }
install -d -m 0700 -o 10001 -g 10001 /srv/sigma-state/auth/operational-logs
install -d -m 0755 /usr/local/libexec/sigma
for script in backend-watchdog.py log-retention.py; do
  install -m 0750 "$repo/deploy/$script" "/usr/local/libexec/sigma/$script"
done
for unit in sigma-backend-watchdog.service sigma-backend-watchdog.timer sigma-log-retention.service sigma-log-retention.timer; do
  install -m 0644 "$repo/deploy/systemd/$unit" "/etc/systemd/system/$unit"
done
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/sigma-{backend-watchdog,log-retention}.{service,timer}
systemctl enable --now sigma-backend-watchdog.timer sigma-log-retention.timer
echo "Watchdog and retention timers installed. Check systemctl list-timers and journalctl."
