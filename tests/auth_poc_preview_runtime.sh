#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
release_sha="${GITHUB_SHA:?GITHUB_SHA must identify the exact tested tree}"
scratch="$(mktemp -d)"
project="sigma-personal-lab-preview-runtime"
edge_key="ci-preview-edge-key-$(printf '%040d' 0)"

cleanup() {
  docker compose --project-name "$project" \
    --file "$root/deploy/auth-poc.preview.compose.yaml" down --remove-orphans >/dev/null 2>&1 || true
  docker network rm sigma_personal_lab >/dev/null 2>&1 || true
  rm -rf "$scratch"
}
trap cleanup EXIT

mkdir -p "$scratch/broker" "$scratch/gateways" "$scratch/workspaces"
docker network create --internal sigma_personal_lab >/dev/null

# Build the real worker image used by the preview service. The test deliberately
# exercises its inherited Docker ENTRYPOINT and the preview-only override.
docker build --platform linux/amd64 \
  --tag "sigma-auth-poc:${release_sha}" \
  --file "$root/auth-poc/Dockerfile" "$root"

export SIGMA_RELEASE="$release_sha"
export SIGMA_DOMAIN="sigma.example.invalid"
export SIGMA_PERSONAL_LAB_EDGE_KEY="$edge_key"
export SIGMA_PERSONAL_LAB_BROKER_DIR="$scratch/broker"
export SIGMA_PERSONAL_LAB_GATEWAY_DIR="$scratch/gateways"
export SIGMA_PERSONAL_LAB_WORKSPACES_DIR="$scratch/workspaces"

docker compose --project-name "$project" \
  --file "$root/deploy/auth-poc.preview.compose.yaml" \
  up --detach --wait --wait-timeout 120

container="$(docker compose --project-name "$project" \
  --file "$root/deploy/auth-poc.preview.compose.yaml" ps --quiet preview)"
test -n "$container"
test "$(docker inspect --format '{{.State.Health.Status}}' "$container")" = healthy
docker inspect --format '{{json .Config.Entrypoint}}' "$container" | \
  python3 -c 'import json,sys; entry=json.load(sys.stdin); assert entry == ["/opt/venv/bin/uvicorn"], entry'

docker exec -i \
  --env SIGMA_PERSONAL_LAB_EDGE_KEY="$edge_key" \
  --env SIGMA_DOMAIN="$SIGMA_DOMAIN" \
  "$container" /opt/venv/bin/python - <<'PY'
import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

base = "http://127.0.0.1:8002"
headers = {
    "Host": os.environ["SIGMA_DOMAIN"],
    "X-Sigma-Personal-Lab-Edge": os.environ["SIGMA_PERSONAL_LAB_EDGE_KEY"],
}
with urlopen(Request(base + "/__personal_lab__/health", headers=headers), timeout=5) as response:
    assert response.status == 200
    assert json.load(response) == {"status": "ok", "service": "sigma-personal-lab-preview"}
with urlopen(Request(base + "/__personal_lab__/", headers=headers), timeout=5) as response:
    body = response.read().decode()
    assert response.status == 200
    assert "Synthetic preview only" in body
    assert "Do not sign in to OpenAI" in body
for path in ("/api/cloud-auth/admin/grants", "/api/health", "/health"):
    try:
        urlopen(Request(base + path, headers=headers), timeout=5)
    except HTTPError as error:
        assert error.code == 404, (path, error.code)
    else:
        raise AssertionError(f"preview exposed a root application route: {path}")
print("PASS actual Compose container serves the synthetic preview on 8002 with no root API")
PY
