#!/bin/sh
# Quiesce both release stacks before rolling back or backing up state.
set -eu
env_file=${SIGMA_DEPLOY_ENV_FILE:-/etc/sigma/deploy.env}
"$(dirname "$0")/compose-gce.sh" stop
if [ -f "$env_file" ] && [ ! -L "$env_file" ] && \
   grep -qx 'SIGMA_PERSONAL_HOSTED_ENABLED=true' "$env_file"; then
  "$(dirname "$0")/compose-personal-gce.sh" stop
fi
systemctl stop sigma-personal-broker.service 2>/dev/null || true
