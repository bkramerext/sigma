#!/bin/sh
# Install the restricted restartable broker for the synthetic acceptance lab.
# /etc/sigma/personal-lab.env must already be root-owned mode 0600 and contain
# only the exact release SHA, broker paths, host, and private edge key.
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root." >&2
  exit 1
fi

env_file=/etc/sigma/personal-lab.env
unit_source=/opt/sigma/personal-lab/release/deploy/auth-poc-preview-broker.service
unit_target=/etc/systemd/system/sigma-personal-lab-broker.service

if [ -L "$env_file" ] || [ ! -f "$env_file" ]; then
  echo "The protected preview environment file is missing or unsafe." >&2
  exit 1
fi
if [ "$(stat -c '%a:%u:%g' "$env_file")" != "600:0:0" ]; then
  echo "The protected preview environment file must be root-owned mode 0600." >&2
  exit 1
fi
if [ -L "$unit_source" ] || [ ! -f "$unit_source" ]; then
  echo "The pinned preview broker unit is missing or unsafe." >&2
  exit 1
fi

install -d -o root -g root -m 0700 /srv/sigma-state/auth/personal-lab/workers
install -d -o 10001 -g 10001 -m 0700 /srv/sigma-state/auth/personal-lab/app/workspaces
install -d -o root -g root -m 0711 /run/sigma-personal-broker /run/sigma-personal-gateways
install -o root -g root -m 0644 "$unit_source" "$unit_target"
systemctl daemon-reload
systemctl enable --now sigma-personal-lab-broker.service
systemctl is-active --quiet sigma-personal-lab-broker.service
