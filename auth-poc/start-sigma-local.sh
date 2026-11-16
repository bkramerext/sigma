#!/usr/bin/env bash
# Legacy developer entrypoint. The supported local experience is ./sigma start --prod.
# Keep this compatibility wrapper thin so there is only one implementation.
set -Eeuo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [[ ${1:-} == "--real-signin-preview" ]]; then
  shift # Historical switch: now included in --prod automatically.
fi
exec "$repo/sigma" start --prod "$@"
