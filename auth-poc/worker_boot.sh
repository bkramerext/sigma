#!/bin/sh
# Host-broker-created per-user workers publish a private Unix relay, never TCP.
# The original standalone synthetic POC has no relay mount and is unchanged.
set -eu
umask 077
if [ -d /run/sigma-personal ]; then
  # A stopped container leaves its bind-mounted socket inode behind. Before
  # restart, unlink only our own stale socket; reject symlinks and foreign files.
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
  if [ "${SIGMA_AUTH_POC_LOCAL_DOCKER:-0}" = "1" ]; then
    # Docker Desktop's shared Mac bind mount rejects chmod(2) on socket nodes.
    # Pre-bind the model UDS so Uvicorn does not chmod the mounted socket.
    /opt/venv/bin/python /opt/sigma/auth-poc/local_uds_uvicorn.py &
  else
    /opt/venv/bin/uvicorn model_gateway:app --uds /run/sigma-personal/model.sock --no-access-log &
  fi
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
