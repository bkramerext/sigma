#!/bin/sh
set -eu

disk=${SIGMA_STATE_DISK_MOUNT:-/srv/sigma-state}
if [ -L "$disk" ]; then
  echo "SIGMA state mount path $disk is a symlink; refusing to start." >&2
  exit 1
fi
if [ ! -d "$disk" ] || ! mountpoint -q "$disk"; then
  echo "SIGMA state disk is not mounted at $disk; refusing to start." >&2
  exit 1
fi
if [ -L "$disk/auth" ]; then
  echo "SIGMA state directory $disk/auth is a symlink; refusing to start." >&2
  exit 1
fi
mkdir -p "$disk/auth"
if [ -L "$disk/auth" ] || [ ! -d "$disk/auth" ]; then
  echo "SIGMA state directory $disk/auth is unsafe; refusing to start." >&2
  exit 1
fi
chmod 0700 "$disk/auth"
chown "${SIGMA_BACKEND_UID:-10001}:${SIGMA_BACKEND_GID:-10001}" "$disk/auth"
export SIGMA_STATE_DISK_MOUNT="$disk"
exec docker compose \
  --project-name sigma \
  --env-file "${SIGMA_DEPLOY_ENV_FILE:-/etc/sigma/deploy.env}" \
  -f deploy/compose.yaml \
  -f deploy/compose.gce.yaml \
  up --detach --no-build
