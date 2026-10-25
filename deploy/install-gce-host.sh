#!/usr/bin/env bash
# Install the reviewed Ubuntu 24.04 GCE host prerequisites. This does not
# configure the data-disk UUID, secrets, DNS, OAuth, or start the SIGMA app.
set -Eeuo pipefail

# Ubuntu 24.04 amd64 package set, locked for reproducible Docker host builds.
# Update only with a reviewed Docker package compatibility refresh.
DOCKER_CE_VERSION='5:29.9.2-1~ubuntu.24.04~noble'
CONTAINERD_VERSION='2.4.2-3~ubuntu.24.04~noble'
BUILDX_VERSION='0.38.1-1~ubuntu.24.04~noble'
COMPOSE_VERSION='5.6.1-1~ubuntu.24.04~noble'

blocked() {
  printf 'BLOCKED: %s\n' "$1" >&2
  exit 2
}
failed() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

[[ -r /etc/os-release ]] || blocked 'host must be Ubuntu 24.04 LTS amd64'
# shellcheck disable=SC1091
. /etc/os-release
[[ ${ID:-} == ubuntu && ${VERSION_ID:-} == 24.04 ]] || blocked 'host must be Ubuntu 24.04 LTS'
[[ $(dpkg --print-architecture) == amd64 ]] || blocked 'host architecture must be amd64'
[[ ${EUID} -eq 0 ]] || blocked 'run this installer as root on the target VM'

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install --yes ca-certificates curl gnupg uidmap dbus-user-session slirp4netns fuse-overlayfs
install -d -m 0755 /etc/apt/keyrings
curl --fail --silent --show-error --location \
  https://download.docker.com/linux/ubuntu/gpg \
  --output /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
architecture=$(dpkg --print-architecture)
# shellcheck disable=SC1091
. /etc/os-release
printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu %s stable\n' \
  "$architecture" "$VERSION_CODENAME" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install --yes \
  "docker-ce=${DOCKER_CE_VERSION}" \
  "docker-ce-cli=${DOCKER_CE_VERSION}" \
  "docker-ce-rootless-extras=${DOCKER_CE_VERSION}" \
  "containerd.io=${CONTAINERD_VERSION}" \
  "docker-buildx-plugin=${BUILDX_VERSION}" \
  "docker-compose-plugin=${COMPOSE_VERSION}"

if ! getent group sigma-sandbox >/dev/null; then
  groupadd --system sigma-sandbox
fi
if ! id sigma-sandbox >/dev/null 2>&1; then
  useradd --create-home --home-dir /home/sigma-sandbox \
    --shell /usr/sbin/nologin --gid sigma-sandbox sigma-sandbox
fi
usermod --shell /usr/sbin/nologin --gid sigma-sandbox --groups sigma-sandbox sigma-sandbox
if getent group docker | cut -d: -f4 | tr ',' '\n' | grep -Fxq sigma-sandbox; then
  gpasswd --delete sigma-sandbox docker >/dev/null
fi
if getent group sudo | cut -d: -f4 | tr ',' '\n' | grep -Fxq sigma-sandbox; then
  gpasswd --delete sigma-sandbox sudo >/dev/null
fi

sandbox_uid=$(id -u sigma-sandbox)
for file in /etc/subuid /etc/subgid; do
  [[ -r $file ]] || failed 'subordinate UID/GID database is unavailable'
  if ! awk -F: -v user=sigma-sandbox '$1 == user { found=1; if ($3 >= 65536) valid=1 } END { exit !(found && valid) }' "$file"; then
    failed 'sigma-sandbox needs at least 65536 subordinate UID/GID IDs; allocate a non-overlapping range before retrying'
  fi
done

install -d -o root -g root -m 0750 /etc/sigma
install -d -o sigma-sandbox -g sigma-sandbox -m 0700 \
  /home/sigma-sandbox/.config \
  /home/sigma-sandbox/.config/systemd \
  /home/sigma-sandbox/.config/systemd/user \
  "/home/sigma-sandbox/.config/systemd/user/docker.service.d"
install -o sigma-sandbox -g sigma-sandbox -m 0600 \
  "$(dirname "$0")/systemd/docker.service.d/sigma-socket.conf" \
  "/home/sigma-sandbox/.config/systemd/user/docker.service.d/sigma-socket.conf"

install -d -o root -g root -m 0755 /srv/sigma-state
install -d -o root -g root -m 0755 /opt/sigma
install -d -o root -g root -m 0755 /usr/local/libexec/sigma
install -m 0755 "$(dirname "$0")/gce_preflight.py" /usr/local/libexec/sigma/gce_preflight.py

sed "s/__SANDBOX_UID__/${sandbox_uid}/g" "$(dirname "$0")/systemd/sigma-sandbox.service.in" \
  > /etc/systemd/system/sigma-sandbox.service
install -o root -g root -m 0644 "$(dirname "$0")/systemd/sigma.service" \
  /etc/systemd/system/sigma.service

systemctl daemon-reload
systemctl enable --now docker.service
loginctl enable-linger sigma-sandbox
systemctl start "user@${sandbox_uid}.service"
user_runtime="/run/user/${sandbox_uid}"
for _ in $(seq 1 30); do
  [[ -S "$user_runtime/bus" ]] && break
  sleep 1
done
[[ -S "$user_runtime/bus" ]] || failed 'sigma-sandbox user manager did not start'
runuser -u sigma-sandbox -- env \
  XDG_RUNTIME_DIR="$user_runtime" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=$user_runtime/bus" \
  /usr/bin/dockerd-rootless-setuptool.sh install
systemctl enable --now sigma-sandbox.service

socket="/run/user/${sandbox_uid}/docker.sock"
ready=0
for _ in $(seq 1 30); do
  if [[ -S $socket ]] && docker --host "unix://$socket" info --format '{{json .SecurityOptions}}' 2>/dev/null | grep -qi rootless; then
    ready=1
    break
  fi
  sleep 2
done
[[ $ready -eq 1 ]] || failed 'dedicated sigma-sandbox daemon did not become ready in rootless mode'

printf 'PASS: Ubuntu host prerequisites and dedicated rootless Docker daemon installed.\n'
printf 'BLOCKED: production startup remains gated until deploy.env, disk mount, secret files, runner images, and release checkout are ready.\n'
printf 'Next: run /usr/local/libexec/sigma/gce_preflight.py; enable sigma.service only after it reports PASS.\n'
printf 'Sandbox socket path and numeric group are available from local account metadata; add them to /etc/sigma/deploy.env without adding credentials.\n'
printf 'No GCP resources, credentials, DNS, OAuth, or application services were changed.\n'
