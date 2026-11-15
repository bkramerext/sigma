#!/usr/bin/env bash
# Legacy developer entrypoint. The supported local experience is ./sigma start --prod.
# Keep this compatibility wrapper thin so there is only one implementation.
set -Eeuo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [[ ${1:-} == "--real-signin-preview" ]]; then
  echo "The real sign-in preview remains disabled. Use ./sigma start --prod for the local browser prototype." >&2
  exit 2
fi
exec "$repo/sigma" start --prod "$@"
