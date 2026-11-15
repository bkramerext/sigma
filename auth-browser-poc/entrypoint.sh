#!/bin/sh
set -eu
# Interactive Chromium and its OAuth listener reside in the same network
# namespace. Neither VNC nor a debugging socket is externally exposed.
Xvfb :99 -screen 0 1280x800x24 -nolisten tcp -noreset >/dev/null 2>&1 &
xvfb=$!
trap 'kill "$xvfb" 2>/dev/null || true' EXIT INT TERM
i=0
while [ "$i" -lt 40 ]; do
    if DISPLAY=:99 xdotool getdisplaygeometry >/dev/null 2>&1; then
        break
    fi
    i=$((i+1))
    sleep 0.25
done
exec python -m uvicorn sigma.auth_browser_poc_worker:app --host 0.0.0.0 --port 8765 --no-access-log
