#!/bin/sh
# Chromium is a distinct container from the OAuth worker. Compose shares the
# NETWORK namespace only, giving both the same 127.0.0.1 address.
set -eu
export DISPLAY=:99 HOME=/tmp
export XDG_CONFIG_HOME=/tmp/sigma-config XDG_CACHE_HOME=/tmp/sigma-cache
umask 077
python3 -c 'import secrets; print(secrets.token_urlsafe(9)[:8])' > /tmp/sigma-vnc-pass
Xvfb :99 -screen 0 1280x800x24 -nolisten tcp >/dev/null 2>&1 &
i=0
while [ ! -S /tmp/.X11-unix/X99 ]; do
  i=$((i+1))
  if [ "$i" -ge 60 ]; then echo "Xvfb did not initialize" >&2; exit 1; fi
  sleep 0.1
done
x11vnc -display :99 -localhost -forever -shared -passwdfile /tmp/sigma-vnc-pass -quiet >/dev/null 2>&1 &
websockify --web=/usr/share/novnc 0.0.0.0:6080 127.0.0.1:5900 >/dev/null 2>&1 &
# Nested Chromium namespaces fail under current Docker security. This
# unsandboxed browser is limited to a synthetic, credential-free laboratory.
exec /usr/bin/chromium --no-first-run --no-default-browser-check \
  --disable-dev-shm-usage --no-sandbox --disable-extensions --password-store=basic \
  --user-data-dir=/tmp/chromium --window-size=1280,800 --app=http://127.0.0.1:8001/
