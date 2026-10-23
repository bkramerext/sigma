#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/.." && pwd)
secrets=${SIGMA_WORKER_SECRETS_FILE:-}
if [[ -z "$secrets" || "$secrets" != /* || ! -f "$secrets" || -L "$secrets" ]]; then
  echo "Set SIGMA_WORKER_SECRETS_FILE to an absolute, protected JSON/.env secrets file." >&2
  exit 2
fi
test "$(stat -c '%a' "$secrets")" = 600 || { echo "Worker secrets file must be mode 0600" >&2; exit 2; }
npm --prefix "$repo_root/frontend" ci
npm --prefix "$repo_root/frontend" run build
npm --prefix "$repo_root/deploy/cloudflare" ci
(cd "$repo_root/deploy/cloudflare" && npm exec -- wrangler deploy --config wrangler.jsonc --secrets-file "$secrets")
