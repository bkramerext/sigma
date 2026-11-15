#!/bin/sh
# Host-broker-created per-user workers expose only private loopback host ports.
# Hosted workers keep their direct Unix-socket relays.
set -eu
umask 077
if [ "${SIGMA_AUTH_POC_LOCAL_DOCKER:-0}" = "1" ]; then
  # Local POC only: Compose publishes these ports on host 127.0.0.1, and the
  # browser shares this worker's private network namespace.
  /opt/venv/bin/uvicorn model_gateway:app --host 0.0.0.0 --port 8002 --no-access-log &
elif [ -d /run/sigma-personal ]; then
  # A stopped container may leave bind-mounted socket inodes behind. Unlink
  # only our own stale model socket; reject symlinks and foreign files.
  /opt/venv/bin/python - <<'PY'
import os
import stat
from pathlib import Path

path = Path("/run/sigma-personal/model.sock")
if path.exists() or path.is_symlink():
    current = path.lstat()
    if not stat.S_ISSOCK(current.st_mode) or current.st_uid != os.geteuid():
        raise SystemExit("Unsafe existing model IPC socket")
    path.unlink()
PY
  /opt/venv/bin/python /opt/sigma/auth-poc/unix_proxy.py &
  /opt/venv/bin/uvicorn model_gateway:app --uds /run/sigma-personal/model.sock --no-access-log &
  i=0
  while [ ! -S /run/sigma-personal/vnc.sock ] || [ ! -S /run/sigma-personal/model.sock ]; do
    i=$((i+1))
    if [ "$i" -ge 100 ]; then
      echo "Private browser/model relays failed to initialize" >&2
      exit 1
    fi
    sleep 0.1
  done
fi
exec /opt/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001 --no-access-log
