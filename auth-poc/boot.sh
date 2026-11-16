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
  if [ "$i" -ge 60 ]; then echo "SIGMA Personal browser: Xvfb did not initialize" >&2; exit 1; fi
  sleep 0.1
done
echo "SIGMA Personal browser: Xvfb ready; starting x11vnc"
# noVNC runs in the user's macOS browser, which already applies Caps Lock to
# typed keysyms. Never toggle a second Caps Lock state in the isolated X server:
# two independent lock states can make lowercase letters arrive as UPPERCASE.
# Also clear stale Shift/lock modifiers on startup before accepting credentials.
x11vnc -display :99 -localhost -forever -shared -skip_lockkeys -clear_all \
  -passwdfile /tmp/sigma-vnc-pass -quiet >/dev/null 2>&1 &
websockify --web=/usr/share/novnc 0.0.0.0:6080 127.0.0.1:5900 >/dev/null 2>&1 &
echo "SIGMA Personal browser: VNC relay launched; starting Chromium"
# Keep Chromium's user namespace + seccomp renderer sandbox enabled.
# The Docker service grants only the namespace syscalls required by Chromium.
# Never add --no-sandbox: the process must fail closed on unsupported hosts.
# Use an app window in both real and synthetic modes: no Chromium tabs,
# address bar, or popup. The local worker's / route redirects straight to
# OpenAI authorization only when the account actually needs it.
# Hide Chromium's hybrid-passkey autofill suggestion, automatic passkey
# upgrades, and password-save UI. The managed profile separately forbids
# passkey storage. Keep WebAuthn available if an account requires MFA;
# Google's own sign-in page may still offer an account-level passkey.
exec /usr/bin/chromium --no-first-run --no-default-browser-check \
  --disable-dev-shm-usage --disable-extensions --password-store=basic \
  --disable-save-password-bubble \
  --enable-features=WebAuthnUsePasskeyFromAnotherDeviceInContextMenu \
  --disable-features=AutofillReintroduceHybridPasskeyDropdownItem,WebAuthnPasskeyUpgrade,WebAuthnAmbientSignin \
  --user-data-dir=/tmp/chromium --window-size=1280,800 \
  --app=http://127.0.0.1:8001/
