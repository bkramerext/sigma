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
# Preserve the existing synthetic lab gate; it cannot share Personal state.
auth_lab=0
if grep -qx 'SIGMA_AUTH_POC_LAB_ENABLED=true' "$env_file"; then
  auth_lab=1
  auth_dir="$disk/auth/auth-poc"
  if [ -L "$auth_dir" ]; then
    echo "Unsafe synthetic auth-lab state directory." >&2
    exit 1
  fi
  mkdir -p "$auth_dir"
  chown 10001:10001 "$auth_dir"
  chmod 0700 "$auth_dir"
fi
personal=0
if grep -qx 'SIGMA_PERSONAL_HOSTED_ENABLED=true' "$env_file"; then
  personal=1
  if [ "$auth_lab" -eq 1 ]; then
    echo "Synthetic auth lab and hosted Personal cannot run together." >&2
    exit 1
  fi
  # Persistent encrypted records and vault keys must never be initialized on
  # an ephemeral image layer. Do not follow symlinks or adopt foreign records.
  for name in personal-shared personal-shared-key; do
    directory="$disk/auth/$name"
    if [ -e "$directory" ] || [ -L "$directory" ]; then
      if [ -L "$directory" ] || [ ! -d "$directory" ] ||
         [ "$(stat -c '%u:%g:%a' "$directory")" != "10001:10001:700" ]; then
        echo "Unsafe hosted Personal credential directory." >&2
        exit 1
      fi
    else
      install -d -o 10001 -g 10001 -m 0700 "$directory"
    fi
  done
  # Bind mounting an empty persistent directory hides the secure directories
  # initialized in the image. The worker requires both to exist as 10001:0700.
  for name in records workspaces; do
    directory="$disk/auth/personal-shared/$name"
    if [ -e "$directory" ] || [ -L "$directory" ]; then
      if [ -L "$directory" ] || [ ! -d "$directory" ] ||
         [ "$(stat -c '%u:%g:%a' "$directory")" != "10001:10001:700" ]; then
        echo "Unsafe hosted Personal workspace directory." >&2
        exit 1
      fi
    else
      install -d -o 10001 -g 10001 -m 0700 "$directory"
    fi
  done
fi
set --
if [ "$auth_lab" -eq 1 ]; then set -- "$@" --auth-poc; fi
if [ "$personal" -eq 1 ]; then set -- "$@" --personal-shared; fi
python3 /opt/sigma/current/deploy/release_image.py verify "$release" "$@"
compose() {
  "$(dirname "$0")/compose-gce.sh" "$@"
}
if [ "$personal" -eq 1 ]; then
  "$(dirname "$0")/compose-personal-gce.sh" up -d --no-build --wait
  systemctl start sigma-personal-broker.service
fi
# Only turn off the fallback Docker edge once the host Caddy service
# has the reviewed HTTPS routes to both private application loopback ports.
if grep -qx 'SIGMA_HOST_DIRECT=true' "$env_file"; then
  if [ ! -f /etc/caddy/Caddyfile ] || [ -L /etc/caddy/Caddyfile ] ||
     [ "$(stat -c '%u' /etc/caddy/Caddyfile)" != 0 ] ||
     ! systemctl is-active --quiet caddy ||
     ! caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1 ||
     ! caddy adapt --config /etc/caddy/Caddyfile --adapter caddyfile 2>/dev/null |
       python3 "$(dirname "$0")/check_host_direct_caddy.py"; then
    echo "Verified direct host Caddy routing is unavailable; refusing to stop edge." >&2
    exit 1
  fi
  compose up -d --no-build --scale edge=0
else
  compose up -d --no-build
fi
set -- --backend-container "$(compose ps -q backend)" \
  --frontend-container "$(compose ps -q frontend)"
if [ "$auth_lab" -eq 1 ]; then
  set -- "$@" --auth-poc-container "$(compose ps -q auth-poc)" \
    --auth-browser-poc-container "$(compose ps -q browser)"
fi
if [ "$personal" -eq 1 ]; then
  set -- "$@" --shared-personal-container \
    "$("$(dirname "$0")/compose-personal-gce.sh" ps -q personal)"
fi
python3 /opt/sigma/current/deploy/release_image.py record "$release" "$@"
