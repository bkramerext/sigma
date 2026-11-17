#!/bin/sh
# Single source of truth for the exact hosted Compose stack. Opt-in direct
# host-Caddy routing must never affect production without an explicit flag.
set -eu
env_file=${SIGMA_DEPLOY_ENV_FILE:-/etc/sigma/deploy.env}
if [ -L "$env_file" ] || [ ! -f "$env_file" ]; then
  echo "Deployment environment file is missing or unsafe." >&2
  exit 1
fi

# Prepend optional overlays, preserving all original Compose arguments.
if grep -q '^SIGMA_INVITATION_GMAIL_TOKEN_FILE_HOST=.' "$env_file"; then
  set -- -f deploy/compose.gmail.yaml "$@"
fi
if grep -qx 'SIGMA_AUTH_POC_LAB_ENABLED=true' "$env_file"; then
  set -- -f deploy/auth-poc.compose.yaml -f deploy/auth-poc.gce.yaml "$@"
fi
if grep -qx 'SIGMA_HOST_DIRECT=true' "$env_file"; then
  set -- -f deploy/compose.direct.gce.yaml "$@"
fi
if grep -qx 'SIGMA_PERSONAL_HOSTED_ENABLED=true' "$env_file"; then
  set -- -f deploy/compose.personal.backend.gce.yaml "$@"
fi

exec docker compose --project-name sigma --env-file "$env_file" \
  -f deploy/compose.yaml -f deploy/compose.gce.yaml "$@"
