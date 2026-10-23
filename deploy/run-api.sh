#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 || "$1" != /* || "$2" != /* ]]; then
  echo "usage: $0 /absolute/path/to/sigma-data /absolute/path/to/runtime.env [image-tag]" >&2
  exit 2
fi
root=$1
env_file=$2
tag=${3:-sigma-api:current}
container=sigma-api
test -d "$root" && test -r "$env_file" && test ! -L "$env_file"
test "$(stat -c '%a' "$env_file")" = 600 || { echo "runtime env file must be mode 0600" >&2; exit 2; }
if docker container inspect "$container" >/dev/null 2>&1; then docker rm -f "$container" >/dev/null; fi
docker run -d --name "$container" --restart unless-stopped \
  --user 10001:10001 --read-only --tmpfs /tmp:rw,noexec,nosuid,size=32m \
  --mount "type=bind,src=$root,dst=/var/lib/sigma" \
  --env-file "$env_file" -e SIGMA_PERSISTENT_DATA_ROOT=/var/lib/sigma \
  -p 127.0.0.1:8000:8000 "$tag" >/dev/null
echo "Started $container as $tag on loopback port 8000."
