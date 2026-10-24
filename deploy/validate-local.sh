#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is required for the local deployment check." >&2
  exit 2
fi
if ! docker info >/dev/null 2>&1; then
  echo "Start a local Docker engine before running this check." >&2
  exit 2
fi

socket=${SIGMA_SANDBOX_DOCKER_SOCKET:-/var/run/docker.sock}
# Compose runs inside the local Linux engine, where this conventional rootful
# engine socket is root-owned. This is only for the isolated smoke test; GCE
# uses the separate rootless sigma-sandbox socket and UID 10001.
socket_gid=0
socket_uid=10001

temporary=$(mktemp -d "$root/deploy/.local-secrets.XXXXXX")
project="sigma-t42-local-$$"
secret_google="$temporary/google-client-secret"
secret_openai="$temporary/openai-api-key"
environment="$temporary/deploy.env"
printf 'local-only-google-secret\n' >"$secret_google"
printf 'local-only-provider-key\n' >"$secret_openai"
chmod 0444 "$secret_google" "$secret_openai"
cat >"$environment" <<EOF
SIGMA_RELEASE=local-check
SIGMA_DOMAIN=localhost
SIGMA_CADDY_SCHEME=http
SIGMA_TLS_EMAIL=local@example.test
SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL=admin@example.test
SIGMA_CLOUD_ADMIN_CONTACT_EMAIL=admin@example.test
GOOGLE_OIDC_CLIENT_ID=local-check.apps.googleusercontent.com
SIGMA_GOOGLE_OIDC_CLIENT_SECRET_FILE=$secret_google
SIGMA_CLOUD_OPENAI_API_KEY_FILE=$secret_openai
SIGMA_CLOUD_USER_SPEND_CEILING_USD=2.00
SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD=15.00
SIGMA_CLOUD_USER_MAX_CONCURRENT=1
SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT=1
SIGMA_CLOUD_USER_MAX_QUEUED=2
SIGMA_CLOUD_GLOBAL_MAX_QUEUED=8
SIGMA_CLOUD_USER_TOKEN_BUDGET=2000000
SIGMA_SANDBOX_DOCKER_SOCKET=$socket
SIGMA_SANDBOX_DOCKER_GID=$socket_gid
SIGMA_BACKEND_UID=$socket_uid
SIGMA_BACKEND_GID=$socket_gid
SIGMA_HTTP_BIND=127.0.0.1
SIGMA_HTTP_PORT=18080
SIGMA_HTTPS_BIND=127.0.0.1
SIGMA_HTTPS_PORT=18443
EOF

compose=(env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL docker compose --project-name "$project" --env-file "$environment" -f "$root/deploy/compose.yaml")
cleanup() {
  "${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$temporary"
}
trap cleanup EXIT

cd "$root"
"${compose[@]}" build backend
"${compose[@]}" build frontend
"${compose[@]}" run --rm --no-deps --cap-add CHOWN --user 0:0 backend \
  python -c "import os; os.chown('/var/lib/sigma-auth', $socket_uid, $socket_gid)"
"${compose[@]}" up --detach
for attempt in $(seq 1 60); do
  if curl --fail --silent -H 'Host: localhost' http://127.0.0.1:18080/ >/dev/null \
    && curl --fail --silent -H 'Host: localhost' http://127.0.0.1:18080/api/cloud-auth/status \
      | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["enabled"] is True and d["ready"] is True'; then
    break
  fi
  if [[ "$attempt" -eq 60 ]]; then
    echo "Local services did not become ready; no logs or credentials are printed." >&2
    exit 1
  fi
  sleep 2
done

"${compose[@]}" exec -T backend python -c \
  'from pathlib import Path; assert list(Path("/var/lib/sigma-auth").glob("*.sqlite3"))'
"${compose[@]}" restart backend >/dev/null
for attempt in $(seq 1 30); do
  if curl --fail --silent -H 'Host: localhost' http://127.0.0.1:18080/api/cloud-auth/status \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["enabled"] is True and d["ready"] is True'; then
    break
  fi
  if [[ "$attempt" -eq 30 ]]; then
    echo "Backend did not recover after restart." >&2
    exit 1
  fi
  sleep 2
done
"${compose[@]}" exec -T backend python -c \
  'from pathlib import Path; assert list(Path("/var/lib/sigma-auth").glob("*.sqlite3"))'
"${compose[@]}" down >/dev/null
"${compose[@]}" up --no-build --detach
for attempt in $(seq 1 30); do
  if curl --fail --silent -H 'Host: localhost' http://127.0.0.1:18080/api/cloud-auth/status \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["enabled"] is True and d["ready"] is True'; then
    break
  fi
  if [[ "$attempt" -eq 30 ]]; then
    echo "Backend did not recover after container recreation." >&2
    exit 1
  fi
  sleep 2
done
"${compose[@]}" exec -T backend python -c \
  'from pathlib import Path; assert list(Path("/var/lib/sigma-auth").glob("*.sqlite3"))'
echo "Local deployment smoke passed: images built, SPA/API healthy, auth SQLite persisted across restart and container recreation. No Google or provider endpoints were called."
