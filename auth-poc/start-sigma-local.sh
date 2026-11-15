#!/usr/bin/env bash
# Opt-in local SIGMA UI POC: existing pill, real split Docker images,
# private Unix browser relay. Synthetic provider sign-in remains disabled.
set -Eeuo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo"
if ! docker info >/dev/null 2>&1; then
  echo "Start Docker Desktop and retry." >&2
  exit 2
fi
if ! command -v git >/dev/null || ! command -v python3 >/dev/null; then
  echo "Git and Python 3 are required for the local container POC." >&2
  exit 2
fi
release=$(git rev-parse --verify HEAD)
[[ "$release" =~ ^[[:xdigit:]]{40}$ ]] || { echo "No pinned SIGMA commit found" >&2; exit 2; }

# New worktrees have their own untracked .venv and node_modules. Prepare
# them once without adding a second user-facing setup procedure.
if [[ ! -d frontend/node_modules/vite || ! -d .venv ]]; then
  echo "Preparing local SIGMA dependencies…"
  ./sigma setup
fi

# Build the same two images used by the hosted broker, without ever opening
# the standalone noVNC port or allowing the Mac-local OpenAI OAuth fallback.
echo "Preparing isolated SIGMA Personal ChatGPT containers…"
docker compose -f deploy/auth-poc.compose.yaml build
docker tag sigma-auth-poc:local "sigma-auth-poc:$release"
docker tag sigma-auth-browser-poc:local "sigma-auth-browser-poc:$release"

umask 077
runtime=$(mktemp -d /tmp/sigma-personal-local.XXXXXXXX)
mkdir -m 0711 "$runtime/broker" "$runtime/gateways"
state_root="$HOME/.sigma/personal-poc-state"
mkdir -p "$state_root"
chmod 0700 "$state_root"
export SIGMA_RELEASE="$release"
export SIGMA_AUTH_BROKER_LOCAL_POC=1
export SIGMA_AUTH_BROKER_STATE_ROOT="$state_root"
export SIGMA_AUTH_BROKER_GATEWAY_ROOT="$runtime/gateways"
export SIGMA_AUTH_BROKER_SOCKET="$runtime/broker/broker.sock"
export SIGMA_AUTH_BROKER_CLIENT_UID="$(id -u)"
export SIGMA_PERSONAL_BROWSER_LAB_ENABLED=1
export SIGMA_PERSONAL_BROWSER_BROKER_SOCKET="$SIGMA_AUTH_BROKER_SOCKET"
export SIGMA_PERSONAL_BROWSER_GATEWAY_ROOT="$SIGMA_AUTH_BROKER_GATEWAY_ROOT"
export SIGMA_AUTH_POC_REAL_SIGNIN=0

cleanup() {
  # Stop only projects whose workspaces were created for this POC run.
  # Never erase the isolated credential state (no down -v).
  for gateway in "$runtime/gateways/"*; do
    [[ -d "$gateway" ]] || continue
    workspace=${gateway##*/}
    [[ "$workspace" =~ ^[a-f0-9]{32}$ ]] || continue
    SIGMA_AUTH_POC_WORKSPACE_ID="$workspace" \
    SIGMA_STATE_DISK_MOUNT="$state_root/$workspace" \
    SIGMA_AUTH_POC_GATEWAY_DIR="$gateway" \
    SIGMA_AUTH_POC_LOCAL_UID="$(id -u)" \
    SIGMA_AUTH_POC_LOCAL_GID="$(id -g)" \
      docker compose --project-name "sigma-personal-$workspace" \
        -f deploy/auth-poc.compose.yaml -f deploy/auth-poc.gce.yaml \
        -f deploy/auth-poc.user.gce.yaml -f deploy/auth-poc.user.local.yaml \
        down --remove-orphans >/dev/null 2>&1 || true
  done
  if [[ -n "${broker_pid:-}" ]]; then
    kill "$broker_pid" 2>/dev/null || true
    wait "$broker_pid" 2>/dev/null || true
  fi
  rm -rf -- "$runtime"
}
trap cleanup EXIT
python3 auth-poc/host_broker.py &
broker_pid=$!
for _ in $(seq 1 100); do
  [[ -S "$SIGMA_AUTH_BROKER_SOCKET" ]] && break
  if ! kill -0 "$broker_pid" 2>/dev/null; then
    echo "Private Docker broker failed to start." >&2
    exit 1
  fi
  sleep 0.1
done
[[ -S "$SIGMA_AUTH_BROKER_SOCKET" ]] || { echo "Private Docker broker unavailable." >&2; exit 1; }
echo "Open SIGMA, then click its existing ChatGPT pill while in Sponsored mode."
echo "This POC runs real Docker browser/worker containers but does not yet enable OpenAI sign-in."
exec_status=0
./sigma start --signin --navigate "$@" || exec_status=$?
exit "$exec_status"
