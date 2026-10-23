#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "usage: $0 <previous-worker-version-id>" >&2
  exit 2
fi
repo_root=$(cd "$(dirname "$0")/.." && pwd)
(cd "$repo_root/deploy/cloudflare" && npm exec -- wrangler rollback "$1" --config wrangler.jsonc)
