#!/bin/sh
# Host-broker-created per-user workers publish a private Unix relay, never TCP.
# The original standalone synthetic POC has no relay mount and is unchanged.
set -eu
if [ -d /run/sigma-personal ]; then
  /opt/venv/bin/python /opt/sigma/auth-poc/unix_proxy.py &
  i=0
  while [ ! -S /run/sigma-personal/vnc.sock ]; do
    i=$((i+1))
    if [ "$i" -ge 60 ]; then
      echo "Private browser relay failed to initialize" >&2
      exit 1
    fi
    sleep 0.1
  done
fi
exec /opt/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001 --no-access-log
