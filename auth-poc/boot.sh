#!/bin/sh
# Chromium is a distinct container from the OAuth worker. Compose shares the
# NETWORK namespace only, giving both the same 127.0.0.1 address.
set -eu
export DISPLAY=:99 HOME=/tmp
export XDG_CONFIG_HOME=/tmp/sigma-config XDG_CACHE_HOME=/tmp/sigma-cache
umask 077
python3 -c 'import secrets; print(secrets.token_urlsafe(9)[:8])' > /tmp/sigma-vnc-pass
echo "SIGMA Personal browser: starting Xvfb" 
Xvfb :99 -screen 0 1280x800x24 -nolisten tcp >/dev/null 2>&1 &
i=0
while [ ! -S /tmp/.X11-unix/X99 ]; do
  i=$((i+1))
  if [ "$i" -ge 60 ]; then echo "Xvfb did not initialize" >&2; exit 1; fi
  sleep 0.1
done
echo "SIGMA Personal browser: Xvfb ready; starting x11vnc"
x11vnc -display :99 -localhost -forever -shared -passwdfile /tmp/sigma-vnc-pass -quiet >/dev/null 2>&1 &
websockify --web=/usr/share/novnc 0.0.0.0:6080 127.0.0.1:5900 >/dev/null 2>&1 &
echo "SIGMA Personal browser: VNC relay launched; starting Chromium"
# Keep Chromium's user namespace + seccomp renderer sandbox enabled.
# The Docker service grants only the namespace syscalls required by Chromium.
# Never add --no-sandbox: the process must fail closed on unsupported hosts.
# Show the address bar while the user authorizes at OpenAI.
if [ "${SIGMA_AUTH_POC_LOCAL_REAL_SIGNIN:-0}" = "1" ]; then
  set -- http://127.0.0.1:8001/
else
  set -- --app=http://127.0.0.1:8001/
fi
exec /usr/bin/chromium --no-first-run --no-default-browser-check \
  --disable-dev-shm-usage --disable-extensions --password-store=basic \
  --user-data-dir=/tmp/chromium --window-size=1280,800 "$@"
