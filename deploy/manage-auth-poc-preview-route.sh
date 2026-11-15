#!/usr/bin/env bash
# Start/stop the same-host, admin-gated synthetic preview without modifying
# /opt/sigma/current or its tracked Caddyfile.
set -Eeuo pipefail

if [[ "$(id -u)" != 0 ]]; then
  echo "Run this preview lifecycle command as root." >&2
  exit 1
fi
if [[ $# != 1 || ( "$1" != start && "$1" != stop ) ]]; then
  echo "Usage: $0 start|stop" >&2
  exit 2
fi

action="$1"
production=/opt/sigma/current
lab=/opt/sigma/personal-lab/release
runtime=/var/lib/sigma-personal-lab/runtime
deploy_env=/etc/sigma/deploy.env
preview_env=/etc/sigma/personal-lab.env
broker_installer="$lab/deploy/install-auth-poc-preview-broker.sh"
route_tool="$lab/deploy/auth-poc-preview-caddy-route.py"
preview_compose="$lab/deploy/auth-poc.preview.compose.yaml"
edge_overlay="$lab/deploy/auth-poc.preview.edge.gce.yaml"
broker_unit=/etc/systemd/system/sigma-personal-lab-broker.service

for path in "$production" "$lab" "$deploy_env" "$preview_env" "$route_tool" \
  "$preview_compose" "$edge_overlay"; do
  [[ -e "$path" && ! -L "$path" ]] || {
    echo "Required preview deployment path is missing or unsafe." >&2
    exit 1
  }
done
[[ "$(stat -c '%a:%u:%g' "$deploy_env")" == "600:0:0" ]] || {
  echo "Production environment file must be root-owned mode 0600." >&2
  exit 1
}
[[ "$(stat -c '%a:%u:%g' "$preview_env")" == "600:0:0" ]] || {
  echo "Preview environment file must be root-owned mode 0600." >&2
  exit 1
}

env_value() {
  awk -F= -v wanted="$1" '$1 == wanted { print substr($0, index($0, "=") + 1); exit }' "$2"
}

production_sha="$(env_value SIGMA_RELEASE "$deploy_env")"
preview_sha="$(env_value SIGMA_RELEASE "$preview_env")"
domain="$(env_value SIGMA_DOMAIN "$deploy_env")"
[[ "$production_sha" =~ ^[0-9a-f]{40}$ && "$preview_sha" =~ ^[0-9a-f]{40}$ ]] || {
  echo "Both production and preview release SHAs must be full commit hashes." >&2
  exit 1
}
[[ -n "$domain" && "$domain" != *$'\n'* ]] || {
  echo "The production domain is missing or invalid." >&2
  exit 1
}
[[ "$(git -C "$production" rev-parse HEAD)" == "$production_sha" ]] || {
  echo "Production checkout does not match its configured exact release SHA." >&2
  exit 1
}
[[ -z "$(git -C "$production" status --porcelain --untracked-files=normal)" ]] || {
  echo "Production release checkout is not clean; refusing preview lifecycle change." >&2
  exit 1
}
[[ "$(git -C "$lab" rev-parse HEAD)" == "$preview_sha" ]] || {
  echo "Preview checkout does not match its configured exact release SHA." >&2
  exit 1
}
[[ -z "$(git -C "$lab" status --porcelain --untracked-files=normal)" ]] || {
  echo "Preview release checkout is not clean; refusing preview lifecycle change." >&2
  exit 1
}

production_compose=(docker compose --project-name sigma --env-file "$deploy_env")
production_files=(
  -f "$production/deploy/compose.yaml"
  -f "$production/deploy/compose.gce.yaml"
)
preview_runtime=(
  docker compose --project-name sigma-personal-lab-preview
  --env-file "$deploy_env" --env-file "$preview_env"
  -f "$preview_compose"
)
edge_preview=("${production_compose[@]}" --env-file "$preview_env" "${production_files[@]}" -f "$edge_overlay")
edge_overlay_attempted=0
runtime_installed=0
broker_installed=0
preview_started=0
network_created=0

rollback_failed_start() {
  local result=$?
  trap - EXIT
  if [[ "$result" != 0 && "$action" == start ]]; then
    set +e
    if ((edge_overlay_attempted)); then
      restore_production_edge >/dev/null 2>&1
    fi
    if ((preview_started)); then
      "${preview_runtime[@]}" down --remove-orphans >/dev/null 2>&1
    fi
    if ((broker_installed)); then
      stop_synthetic_workers >/dev/null 2>&1
      systemctl disable --now sigma-personal-lab-broker.service >/dev/null 2>&1
      rm -f "$broker_unit"
      systemctl daemon-reload >/dev/null 2>&1
    fi
    if ((runtime_installed)); then
      python3 "$route_tool" rollback --runtime-root "$runtime" >/dev/null 2>&1
    fi
    if ((network_created)); then
      docker network rm sigma_personal_lab >/dev/null 2>&1
    fi
    echo "Preview start failed; attempted isolated rollback. Verify production edge health." >&2
  fi
  return "$result"
}
trap rollback_failed_start EXIT

wait_healthy() {
  local compose=()
  compose=("$@")
  local container status attempt
  container="$("${compose[@]}" ps --quiet edge 2>/dev/null || true)"
  [[ -n "$container" ]] || { echo "Production edge container is missing." >&2; return 1; }
  for attempt in $(seq 1 60); do
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null || true)"
    [[ "$status" == healthy || "$status" == running ]] && return 0
    sleep 2
  done
  echo "Production edge did not become healthy." >&2
  return 1
}

verify_production_and_preview() {
  local api_status preview_status
  api_status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' "https://$domain/api/health")"
  preview_status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' "https://$domain/__personal_lab__/")"
  [[ "$api_status" == 401 ]] || {
    echo "Production unauthenticated API health returned unexpected HTTP $api_status." >&2
    return 1
  }
  [[ "$preview_status" == 401 || "$preview_status" == 403 ]] || {
    echo "Anonymous preview gate returned unexpected HTTP $preview_status." >&2
    return 1
  }
}

restore_production_edge() {
  "${production_compose[@]}" "${production_files[@]}" up -d --no-deps --force-recreate edge
  wait_healthy "${production_compose[@]}" "${production_files[@]}"
}

start_preview() {
  [[ ! -e "$runtime" && ! -L "$runtime" ]] || {
    echo "Preview runtime overlay already exists; inspect before changing it." >&2
    return 1
  }
  if docker network inspect sigma_personal_lab >/dev/null 2>&1; then
    [[ "$(docker network inspect --format '{{.Internal}}' sigma_personal_lab)" == true ]] || {
      echo "Existing sigma_personal_lab network is not internal." >&2
      return 1
    }
  else
    docker network create --internal sigma_personal_lab >/dev/null
    network_created=1
  fi

  docker build --pull --platform linux/amd64 \
    --tag "sigma-auth-poc:$preview_sha" \
    --file "$lab/auth-poc/Dockerfile" "$lab"
  docker build --pull --platform linux/amd64 \
    --tag "sigma-auth-browser-poc:$preview_sha" \
    --file "$lab/auth-poc/browser.Dockerfile" "$lab"
  runtime_installed=1
  python3 "$route_tool" install \
    --caddyfile "$production/deploy/Caddyfile" \
    --snippet "$lab/deploy/auth-poc.preview.caddy" \
    --env-file "$preview_env" --runtime-root "$runtime"
  broker_installed=1
  "$lab/deploy/install-auth-poc-preview-broker.sh"
  systemctl is-active --quiet sigma-personal-lab-broker.service

  preview_started=1
  SIGMA_RELEASE="$preview_sha" "${preview_runtime[@]}" up -d --wait --wait-timeout 120
  edge_overlay_attempted=1
  "${edge_preview[@]}" up -d --no-deps --force-recreate edge
  wait_healthy "${edge_preview[@]}"
  verify_production_and_preview
  [[ -z "$(git -C "$production" status --porcelain --untracked-files=normal)" ]] || {
    echo "Preview setup changed the production release checkout." >&2
    return 1
  }
  echo "PASS: private synthetic preview is running; anonymous preview is blocked and production health is unchanged."
}

stop_preview() {
  [[ -d "$runtime" && ! -L "$runtime" ]] || {
    echo "Preview runtime overlay is not installed." >&2
    return 1
  }
  # Recreate the edge with its normal release Caddyfile before stopping the
  # upstream. This removes only the preview route and keeps the production API.
  restore_production_edge
  local route_status api_status page
  route_status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' "https://$domain/__personal_lab__/")"
  api_status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' "https://$domain/api/health")"
  [[ "$route_status" == 200 && "$api_status" == 401 ]] || {
    echo "Restored production routing returned unexpected statuses ($route_status, $api_status)." >&2
    return 1
  }
  page="$(curl --silent --show-error "https://$domain/__personal_lab__/")"
  [[ "$page" == *"SIGMA · Research workspace"* && "$page" != *"Synthetic preview only"* ]] || {
    echo "Restored path does not serve the production application." >&2
    return 1
  }
  "${preview_runtime[@]}" down --remove-orphans
  stop_synthetic_workers
  systemctl disable --now sigma-personal-lab-broker.service
  rm -f "$broker_unit"
  systemctl daemon-reload
  python3 "$route_tool" rollback --runtime-root "$runtime"
  docker network rm sigma_personal_lab >/dev/null
  [[ -z "$(git -C "$production" status --porcelain --untracked-files=normal)" ]] || {
    echo "Preview teardown changed the production release checkout." >&2
    return 1
  }
  echo "PASS: preview stopped; normal production route, API, edge health and clean release checkout restored."
}

stop_synthetic_workers() {
  local workspace_root=/srv/sigma-state/auth/personal-lab/workers
  local gateway_root=/run/sigma-personal-gateways
  local edge_key workspace_id
  edge_key="$(env_value SIGMA_PERSONAL_LAB_EDGE_KEY "$preview_env")"
  [[ -d "$workspace_root" && ! -L "$workspace_root" ]] || return 0
  while IFS= read -r workspace_id; do
    [[ "$workspace_id" =~ ^[0-9a-f]{32}$ ]] || continue
    SIGMA_RELEASE="$preview_sha" \
      SIGMA_STATE_DISK_MOUNT="$workspace_root/$workspace_id" \
      SIGMA_AUTH_POC_GATEWAY_DIR="$gateway_root/$workspace_id" \
      SIGMA_AUTH_BROKER_ISOLATED_NETWORK=1 \
      SIGMA_DOMAIN="$domain" \
      SIGMA_PERSONAL_LAB_EDGE_KEY="$edge_key" \
      docker compose --project-name "sigma-personal-$workspace_id" \
        -f "$lab/deploy/auth-poc.compose.yaml" \
        -f "$lab/deploy/auth-poc.gce.yaml" \
        -f "$lab/deploy/auth-poc.user.gce.yaml" \
        -f "$lab/deploy/auth-poc.preview.worker.gce.yaml" \
        down --remove-orphans >/dev/null
  done < <(python3 - "$workspace_root" <<'PY'
import os
import re
import sys

root = sys.argv[1]
for entry in os.scandir(root):
    if entry.is_dir(follow_symlinks=False) and re.fullmatch(r"[0-9a-f]{32}", entry.name):
        print(entry.name)
PY
  )
}

if [[ "$action" == start ]]; then
  start_preview
else
  stop_preview
fi
