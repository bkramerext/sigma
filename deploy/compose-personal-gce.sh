#!/bin/sh
# Operate only the standalone, host-loopback Personal worker Compose project.
set -eu
env_file=${SIGMA_DEPLOY_ENV_FILE:-/etc/sigma/deploy.env}
if [ -L "$env_file" ] || [ ! -f "$env_file" ]; then
  echo "Protected Personal deployment environment missing." >&2
  exit 1
fi
if ! grep -qx 'SIGMA_PERSONAL_HOSTED_ENABLED=true' "$env_file"; then
  echo "Hosted Personal worker is disabled." >&2
  exit 1
fi
checkout=$(sed -n 's/^SIGMA_AUTH_POC_CHECKOUT_ID=//p' "$env_file")
if ! printf '%s\n' "$checkout" | grep -Eq '^[0-9a-f]{32}$'; then
  echo "Hosted Personal checkout ID is invalid." >&2
  exit 1
fi
export SIGMA_AUTH_POC_CHECKOUT_ID="$checkout"
exec docker compose --project-name "sigma-shared-$checkout" --env-file "$env_file" \
  -f deploy/personal-shared.compose.yaml -f deploy/personal-shared.gce.yaml "$@"
