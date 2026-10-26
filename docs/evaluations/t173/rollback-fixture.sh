#!/usr/bin/env bash
# Exercise the real rollback helper inside a disposable Linux container. All
# host-specific commands are fixture stubs and all /etc, /srv, /var writes stay
# inside the throwaway container.
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
image=${SIGMA_ROLLBACK_FIXTURE_IMAGE:-sigma-backend:local-check}
docker run --rm --platform linux/amd64 --user 0:0 -i \
  -v "$root/deploy/rollback-gce-release.sh:/tmp/rollback-gce-release.sh:ro" \
  "$image" bash -s <<'CONTAINER'
set -euo pipefail
old=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
previous=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
mkdir -p /etc/sigma /srv/sigma-state /usr/local/libexec/sigma /tmp/fixture-bin
printf 'SIGMA_RELEASE=%s\nSIGMA_STATE_DISK_MOUNT=/srv/sigma-state\n' "$old" >/etc/sigma/deploy.env
chmod 0600 /etc/sigma/deploy.env
printf 'persistent fixture bytes\n' >/srv/sigma-state/sentinel

cat >/tmp/fixture-bin/findmnt <<'SH'
#!/bin/sh
printf '/srv/sigma-state\n'
SH
cat >/tmp/fixture-bin/systemctl <<'SH'
#!/bin/sh
if [ "$1" = is-active ]; then exit 1; fi
if [ "$1" = restart ]; then exit 0; fi
exit 0
SH
cat >/tmp/fixture-bin/docker <<'SH'
#!/bin/sh
case "$1 $2" in
  'image inspect') exit 0 ;;
  'compose --project-name')
    case " $* " in
      *' ps -q backend '*) echo backend-id ;;
      *' ps -q frontend '*) echo frontend-id ;;
      *' ps -q edge '*) echo edge-id ;;
    esac
    exit 0 ;;
esac
if [ "$1" = inspect ] && [ "$2" = -f ]; then
  case "$4" in
    backend-id|frontend-id) printf '%s\n' "$FIXTURE_HEALTH" ;;
    edge-id) printf 'running\n' ;;
  esac
  exit 0
fi
exit 0
SH
cat >/tmp/fixture-bin/sleep <<'SH'
#!/bin/sh
exit 0
SH
cat >/tmp/fixture-bin/logger <<'SH'
#!/bin/sh
exit 0
SH
chmod +x /tmp/fixture-bin/*
cat >/usr/local/libexec/sigma/gce_preflight.py <<'SH'
#!/bin/sh
exit 0
SH
chmod +x /usr/local/libexec/sigma/gce_preflight.py
export PATH="/tmp/fixture-bin:$PATH"
state_before=$(sha256sum /srv/sigma-state/sentinel | cut -d' ' -f1)

export FIXTURE_HEALTH=unhealthy
if /bin/bash /tmp/rollback-gce-release.sh "$previous" --backup-verified --schema-compatible \
  >/tmp/rollback-failure.out 2>/tmp/rollback-failure.err; then
  echo 'FAIL: failed-health rollback unexpectedly succeeded'
  exit 1
fi
grep -q 'candidate container health checks failed' /tmp/rollback-failure.err
test "$(sed -n '1p' /etc/sigma/deploy.env)" = "SIGMA_RELEASE=$old"
test "$(sha256sum /srv/sigma-state/sentinel | cut -d' ' -f1)" = "$state_before"
echo 'PASS failed-health branch restored original SHA and preserved state sentinel'

export FIXTURE_HEALTH=healthy
/bin/bash /tmp/rollback-gce-release.sh "$previous" --backup-verified --schema-compatible \
  >/tmp/rollback-success.out
test "$(sed -n '1p' /etc/sigma/deploy.env)" = "SIGMA_RELEASE=$previous"
test "$(sha256sum /srv/sigma-state/sentinel | cut -d' ' -f1)" = "$state_before"
cat /tmp/rollback-success.out
echo 'PASS successful rollback selected previous SHA and preserved state sentinel'
CONTAINER
