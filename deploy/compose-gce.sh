#!/bin/sh
# Single source of truth for the exact production Compose stack. Used for
# startup, shutdown, health/record queries, and backup's systemd ExecStop.
set -eu
env_file=${SIGMA_DEPLOY_ENV_FILE:-/etc/sigma/deploy.env}
if [ -L "$env_file" ] || [ ! -f "$env_file" ]; then
  echo "Deployment environment file is missing or unsafe." >&2
  exit 1
fi
if grep -qx 'SIGMA_AUTH_POC_LAB_ENABLED=true' "$env_file"; then
  if grep -q '^SIGMA_INVITATION_GMAIL_TOKEN_FILE_HOST=.' "$env_file"; then
    exec docker compose --project-name sigma --env-file "$env_file" \
      -f deploy/compose.yaml -f deploy/compose.gce.yaml \
      -f deploy/auth-poc.compose.yaml -f deploy/auth-poc.gce.yaml \
      -f deploy/compose.gmail.yaml "$@"
  fi
  exec docker compose --project-name sigma --env-file "$env_file" \
    -f deploy/compose.yaml -f deploy/compose.gce.yaml \
    -f deploy/auth-poc.compose.yaml -f deploy/auth-poc.gce.yaml "$@"
fi
if grep -q '^SIGMA_INVITATION_GMAIL_TOKEN_FILE_HOST=.' "$env_file"; then
  exec docker compose --project-name sigma --env-file "$env_file" \
    -f deploy/compose.yaml -f deploy/compose.gce.yaml \
    -f deploy/compose.gmail.yaml "$@"
fi
exec docker compose --project-name sigma --env-file "$env_file" \
  -f deploy/compose.yaml -f deploy/compose.gce.yaml "$@"
