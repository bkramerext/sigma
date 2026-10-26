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
env_file=${SIGMA_DEPLOY_ENV_FILE:-/etc/sigma/deploy.env}
if [ -L "$env_file" ] || [ ! -f "$env_file" ]; then
  echo "Deployment environment file is missing or unsafe." >&2
  exit 1
fi
release=$(sed -n 's/^SIGMA_RELEASE=//p' "$env_file")
release_count=$(grep -c '^SIGMA_RELEASE=' "$env_file" || true)
if [ "$release_count" -ne 1 ]; then
  echo "SIGMA_RELEASE must be set exactly once; refusing to start." >&2
  exit 1
fi
python3 /opt/sigma/current/deploy/release_image.py verify "$release"
compose() {
  docker compose --project-name sigma --env-file "$env_file" \
    -f deploy/compose.yaml -f deploy/compose.gce.yaml "$@"
}
compose up -d --no-build
python3 /opt/sigma/current/deploy/release_image.py record "$release" \
  --backend-container "$(compose ps -q backend)" \
  --frontend-container "$(compose ps -q frontend)"
