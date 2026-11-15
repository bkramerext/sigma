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
Xvfb :99 -screen 0 1280x800x24 -nolisten tcp >/dev/null 2>&1 &
xvfb_pid=$!
x11vnc -display :99 -localhost -forever -shared -nopw -quiet >/dev/null 2>&1 &
vnc_pid=$!
websockify --web=/usr/share/novnc 0.0.0.0:6080 127.0.0.1:5900 >/dev/null 2>&1 &
web_pid=$!
trap 'kill "$xvfb_pid" "$vnc_pid" "$web_pid" 2>/dev/null || true' EXIT INT TERM
# OpenAI authentication is initiated only by the user from the remote Chromium.
# The API is not published; only Chromium within the container can reach it.
exec /opt/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001 --no-access-log
