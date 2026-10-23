#!/usr/bin/env bash
set -euo pipefail
tag=${1:-sigma-api:current}
repo_root=$(cd "$(dirname "$0")/.." && pwd)
docker build --pull -f "$repo_root/deploy/Dockerfile" -t "$tag" "$repo_root"
