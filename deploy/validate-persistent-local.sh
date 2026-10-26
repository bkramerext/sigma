#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if ! docker info >/dev/null 2>&1; then
  echo "Start a local Docker engine before this check." >&2
  exit 2
fi
port=${SIGMA_T100_CONTAINER_PORT:-18089}
python3 - "$port" <<'PY'
import socket, sys
with socket.socket() as listener:
    try:
        listener.bind(("127.0.0.1", int(sys.argv[1])))
    except OSError:
        raise SystemExit("T100 container check port is occupied")
PY

image=sigma-t100-local:check
volume=sigma-t100-state-$$
container=sigma-t100-backend-$$
cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
  docker volume rm "$volume" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker build -t "$image" -f "$root/Dockerfile" "$root"
docker volume create "$volume" >/dev/null
docker run --rm --user 0:0 -v "$volume:/state" "$image" \
  sh -c 'chmod 0700 /state && chown 10001:10001 /state'

start_backend() {
  docker run --detach --name "$container" --no-healthcheck \
    --publish "127.0.0.1:$port:8000" \
    --volume "$volume:/var/lib/sigma-auth" \
    --env SIGMA_STORAGE_BACKEND=persistent_disk \
    --env SIGMA_STORAGE_ROOT=/var/lib/sigma-auth \
    --env SIGMA_CLOUD_AUTH_HOME=/var/lib/sigma-auth \
    --env SIGMA_CLOUD_WORKSPACES_ROOT=/var/lib/sigma-auth/workspaces \
    --env SIGMA_CLOUD_AUTH_ENABLED=true \
    --env SIGMA_CLOUD_PUBLIC_ORIGIN=https://sigma.test \
    --env SIGMA_CLOUD_ADMIN_CONTACT_EMAIL=admin@example.test \
    --env GOOGLE_OIDC_CLIENT_ID=fixture.apps.googleusercontent.com \
    --env GOOGLE_OIDC_CLIENT_SECRET=fixture-only-no-network \
    "$image" >/dev/null
}

wait_backend() {
  python3 - "http://127.0.0.1:$port/api/cloud-auth/status" <<'PY'
import json, sys, time, urllib.error, urllib.request
url = sys.argv[1]
for _ in range(100):
    try:
        with urllib.request.urlopen(url, timeout=0.4) as response:
            body = json.load(response)
        if body.get("enabled") and body.get("ready") and body.get("target") == "hosted":
            break
    except (OSError, urllib.error.URLError, ValueError):
        time.sleep(0.2)
else:
    raise SystemExit("Persistent-disk container did not become ready")
PY
  docker exec "$container" test -f /var/lib/sigma-auth/access.sqlite3
}

start_backend
wait_backend
docker restart "$container" >/dev/null
wait_backend
docker rm -f "$container" >/dev/null
start_backend
wait_backend
echo "PASS local persistent_disk container smoke: auth database persisted on a private Docker volume through backend restart and container recreation; fixture credentials only, no OAuth exchange or inference."
