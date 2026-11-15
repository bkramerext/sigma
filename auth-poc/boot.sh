#!/bin/sh
# All browser and callback activity stays in this container's network namespace.
# Port 6080 is published only on the host LOOPBACK interface by Compose.
set -eu
export DISPLAY=:99
export HOME=/tmp
export XDG_CONFIG_HOME=/tmp/sigma-config
export XDG_CACHE_HOME=/tmp/sigma-cache
export SIGMA_CLOUD_AUTH_ENABLED=false
export SIGMA_CLOUD_AUTH_LOCAL=false
export SIGMA_STORAGE_BACKEND=local
# A browser tab on the host must not be able to attach to another tab's VNC
# session without an explicit, random per-container password.
umask 077
/opt/venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(9)[:12])' > /tmp/sigma-vnc-pass
Xvfb :99 -screen 0 1280x800x24 -nolisten tcp >/dev/null 2>&1 &
xvfb_pid=$!
# Wait for the X socket before connecting VNC to Xvfb.
i=0
while [ ! -S /tmp/.X11-unix/X99 ]; do
    i=$((i+1))
    if [ "$i" -ge 60 ]; then echo "Xvfb did not initialize" >&2; exit 1; fi
    sleep 0.1
done
x11vnc -display :99 -localhost -forever -shared -passwdfile /tmp/sigma-vnc-pass -quiet >/dev/null 2>&1 &
vnc_pid=$!
websockify --web=/usr/share/novnc 0.0.0.0:6080 127.0.0.1:5900 >/dev/null 2>&1 &
web_pid=$!
trap 'kill "$xvfb_pid" "$vnc_pid" "$web_pid" 2>/dev/null || true' EXIT INT TERM
# OpenAI authentication is initiated only by the user from the remote Chromium.
# The API is not published; only Chromium within the container can reach it.
exec /opt/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001 --no-access-log
