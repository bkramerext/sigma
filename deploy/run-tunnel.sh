#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 || "$1" != /* || ! -f "$1" || -L "$1" ]]; then
  echo "usage: $0 /absolute/path/to/cloudflare-tunnel-token" >&2
  exit 2
fi
token=$1
test "$(stat -c '%a' "$token")" = 640 || { echo "tunnel token file must be mode 0640" >&2; exit 2; }
test "$(stat -c '%g' "$token")" = 65532 || { echo "tunnel token file must be group 65532" >&2; exit 2; }
docker rm -f sigma-tunnel >/dev/null 2>&1 || true
docker run -d --name sigma-tunnel --restart unless-stopped --network host \
  --user 65532:65532 --read-only --tmpfs /tmp:rw,noexec,nosuid,size=8m \
  --cap-drop ALL --security-opt no-new-privileges:true \
  --mount "type=bind,src=$token,dst=/run/secrets/tunnel-token,readonly" \
  cloudflare/cloudflared:2026.10.0@sha256:9b49eed8f62806d5d45ddf59ecefb5710429598ea6d3fcccd2af938f621b2b07 \
  tunnel --no-autoupdate run --token-file /run/secrets/tunnel-token >/dev/null
echo "Started pinned cloudflared tunnel container."
