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
# The port can differ for separately provisioned experimental workers.
port=${SIGMA_AUTH_POC_PORT:-16080}
[[ "$port" =~ ^[0-9]+$ ]] && ((port >= 1024 && port <= 65535)) || {
  echo "Invalid experimental browser port." >&2; exit 2;
}
docker compose -f deploy/auth-poc.compose.yaml up -d --build --wait
password=$(docker compose -f deploy/auth-poc.compose.yaml exec -T browser cat /tmp/sigma-vnc-pass | tr -d '\r')
printf '\nSIGMA containerized ChatGPT POC is ready.\n'
printf 'Open http://127.0.0.1:${port}/vnc.html\n'
printf 'Remote browser password: %s\n' "$password"
printf 'Synthetic lab only: real OpenAI sign-in is disabled pending security review.\n'
printf 'Stop with: docker compose -f deploy/auth-poc.compose.yaml down\n'
if command -v open >/dev/null 2>&1; then
  open "http://127.0.0.1:16080/vnc.html"
fi
