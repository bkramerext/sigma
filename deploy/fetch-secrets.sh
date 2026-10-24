#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: sudo $0 PROJECT_ID GOOGLE_OAUTH_SECRET_NAME OPENAI_API_KEY_SECRET_NAME" >&2
  exit 2
fi

project_id=$1
google_secret=$2
openai_secret=$3
secret_dir=/run/sigma-secrets
tmp_dir=$(mktemp -d /run/sigma-secrets.XXXXXX)
trap 'rm -rf "$tmp_dir"' EXIT
install -d -o root -g root -m 0700 "$secret_dir"

# Run as root on the VM so mounted Compose files can be owned by the app's
# container UID. gcloud uses the attached VM service account via metadata.
gcloud secrets versions access latest --secret="$google_secret" --project="$project_id" \
  >"$tmp_dir/google-oauth-client-secret"
gcloud secrets versions access latest --secret="$openai_secret" --project="$project_id" \
  >"$tmp_dir/openai-api-key"
install -o 10001 -g 10001 -m 0400 "$tmp_dir/google-oauth-client-secret" \
  "$secret_dir/google-oauth-client-secret.new"
install -o 10001 -g 10001 -m 0400 "$tmp_dir/openai-api-key" \
  "$secret_dir/openai-api-key.new"
mv -f "$secret_dir/google-oauth-client-secret.new" "$secret_dir/google-oauth-client-secret"
mv -f "$secret_dir/openai-api-key.new" "$secret_dir/openai-api-key"
echo "Mounted production secrets refreshed. Restart the backend service to apply them."
