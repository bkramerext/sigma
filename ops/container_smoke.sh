#!/usr/bin/env bash
set -euo pipefail

tag=${1:-sigma-api:t22-smoke}
volume="sigma-smoke-$RANDOM-$$"
container="sigma-smoke-$RANDOM-$$"
temporary=$(mktemp -d)
cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
  docker volume rm "$volume" >/dev/null 2>&1 || true
  rm -rf "$temporary"
}
trap cleanup EXIT
docker volume create "$volume" >/dev/null
docker run --rm --user 0 -v "$volume:/var/lib/sigma" --entrypoint /bin/sh "$tag" -c \
  'chown 10001:10001 /var/lib/sigma && chmod 700 /var/lib/sigma && printf "SIGMA durable cloud data volume v1\\n" > /var/lib/sigma/.sigma-deployment-volume-v1 && chown 10001:10001 /var/lib/sigma/.sigma-deployment-volume-v1 && chmod 600 /var/lib/sigma/.sigma-deployment-volume-v1'
cat > "$temporary/runtime.env" <<'EOF'
SIGMA_CLOUD_AUTH_ENABLED=true
GOOGLE_OIDC_CLIENT_ID=deployment-fixture.apps.googleusercontent.com
GOOGLE_OIDC_CLIENT_SECRET=deterministic-no-provider-use
SIGMA_CLOUD_PUBLIC_ORIGIN=https://sigma.example.test
SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL=admin@example.test
SIGMA_CLOUD_ADMIN_CONTACT_EMAIL=admin@example.test
SIGMA_CLOUD_AUTH_HOME=/var/lib/sigma/auth
SIGMA_CLOUD_WORKSPACES_ROOT=/var/lib/sigma/workspaces
SIGMA_CLOUD_DEMO_AUDIT=/app/cloud-demo/handshake-demo-audit.json
EOF
chmod 600 "$temporary/runtime.env"
docker run -d --name "$container" --user 10001:10001 --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=32m -v "$volume:/var/lib/sigma" \
  --env-file "$temporary/runtime.env" -e SIGMA_PERSISTENT_DATA_ROOT=/var/lib/sigma \
  -p 127.0.0.1:18080:8000 "$tag" >/dev/null
for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:18080/api/cloud-auth/status -o "$temporary/status.json"; then break; fi
  sleep 1
done
python3 - "$temporary/status.json" <<'PY'
import json, sys
status = json.load(open(sys.argv[1]))
assert status["enabled"] is True and status["ready"] is True
PY
curl -fsS http://127.0.0.1:18080/api/cloud-demo/ -o "$temporary/audit.json"
for format in txt html tex; do
  curl -fsS "http://127.0.0.1:18080/api/cloud-demo/report?format=$format" -o "$temporary/report.$format"
done
python3 - "$temporary" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
audit = json.loads((root / "audit.json").read_text())
assert audit["export_version"] == 2
assert "Research problem:" in (root / "report.txt").read_text()
assert "<!doctype html>" in (root / "report.html").read_text()
assert "\\documentclass" in (root / "report.tex").read_text()
PY
status=$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:18080/api/projects/recent)
test "$status" = 401
status=$(curl -sS -o /dev/null -w '%{http_code}' -X POST -H 'Origin: https://sigma.example.test' -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:18080/api/projects/init)
test "$status" = 401
before=$(docker exec "$container" sha256sum /var/lib/sigma/auth/access.sqlite3 | cut -d' ' -f1)
docker restart "$container" >/dev/null
for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:18080/api/cloud-auth/status -o "$temporary/status-after-restart.json"; then break; fi
  sleep 1
done
after=$(docker exec "$container" sha256sum /var/lib/sigma/auth/access.sqlite3 | cut -d' ' -f1)
test "$before" = "$after"
docker stop "$container" >/dev/null

grep -v '^GOOGLE_OIDC_CLIENT_SECRET=' "$temporary/runtime.env" > "$temporary/missing-secret.env"
if docker run --rm --entrypoint /app/.venv/bin/python --user 10001:10001 -v "$volume:/var/lib/sigma" --env-file "$temporary/missing-secret.env" -e SIGMA_PERSISTENT_DATA_ROOT=/var/lib/sigma "$tag" -m sigma.deployment true > "$temporary/missing.log" 2>&1; then exit 1; else test "$?" = 78; fi
grep -q 'configuration or persistent storage is invalid' "$temporary/missing.log"
if docker run --rm --entrypoint /app/.venv/bin/python --user 10001:10001 -v "$volume:/var/lib/sigma" --env-file "$temporary/runtime.env" -e SIGMA_CLOUD_PUBLIC_ORIGIN=http://sigma.example.test -e SIGMA_PERSISTENT_DATA_ROOT=/var/lib/sigma "$tag" -m sigma.deployment true > "$temporary/invalid-origin.log" 2>&1; then exit 1; else test "$?" = 78; fi
echo "production container checks passed: Demo/exports, private API denial, restart persistence, missing-secret and invalid-origin fail-closed"
