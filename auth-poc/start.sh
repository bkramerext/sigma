#!/usr/bin/env bash
# Local developer convenience wrapper. The Docker image and its startup are
# identical on Mac and GCE; this wrapper is NOT a runtime component.
set -Eeuo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
if ! docker info >/dev/null 2>&1; then
  echo "Docker Desktop or a Docker daemon must be running." >&2
  exit 2
fi
docker compose -f deploy/auth-poc.compose.yaml up -d --build --wait
password=$(docker compose -f deploy/auth-poc.compose.yaml exec -T auth-poc cat /tmp/sigma-vnc-pass | tr -d '\r')
printf '\nSIGMA containerized ChatGPT POC is ready.\n'
printf 'Open http://127.0.0.1:16080/vnc.html\n'
printf 'Remote browser password: %s\n' "$password"
printf 'In the remote Chromium, click Open ChatGPT account chooser.\n'
printf 'Stop with: docker compose -f deploy/auth-poc.compose.yaml down\n'
if command -v open >/dev/null 2>&1; then
  open "http://127.0.0.1:16080/vnc.html"
fi
