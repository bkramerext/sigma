#!/usr/bin/env bash
# Build the bounded research images only through sigma-sandbox's rootless daemon.
set -Eeuo pipefail

if [[ $(id -un) != sigma-sandbox ]]; then
  echo "FAIL: run this script as the dedicated sigma-sandbox account." >&2
  exit 1
fi

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
uid=$(id -u)
socket="/run/user/${uid}/docker.sock"
export DOCKER_HOST="unix://${socket}"

if [[ ! -S $socket ]]; then
  echo "BLOCKED: the dedicated rootless Docker socket is unavailable." >&2
  exit 2
fi
security_options=$(docker info --format '{{json .SecurityOptions}}')
if ! grep -qi rootless <<<"$security_options"; then
  echo "FAIL: the selected research daemon does not report rootless mode." >&2
  exit 1
fi

docker build --platform linux/amd64 \
  --tag sigma-research-python:0.1 \
  --file "$root/sandbox-poc/Dockerfile" "$root/sandbox-poc"
docker build --platform linux/amd64 \
  --tag sigma-research-sage:10.8 \
  --file "$root/sandbox-poc/Dockerfile.sage" "$root/sandbox-poc"
docker image inspect sigma-research-python:0.1 sigma-research-sage:10.8 >/dev/null
printf 'PASS: Python and SageMath runner images built and inspected through the rootless sandbox daemon.\n'
