#!/bin/sh
# In the shared low-memory POC, Chromium runs under a different Linux UID
# inside the same Docker container as the OAuth worker. Its HOME/profile are
# disposable; it never mounts the protected token or key directories.
set -eu
export DISPLAY=:99 HOME="${SIGMA_BROWSER_HOME:-/tmp}"
export XDG_CONFIG_HOME="$HOME/sigma-config" XDG_CACHE_HOME="$HOME/sigma-cache"
BROWSER_PROFILE="${SIGMA_BROWSER_PROFILE:-/tmp/chromium}"
BROWSER_PASSWORD_PATH="${SIGMA_BROWSER_PASSWORD_PATH:-/tmp/sigma-vnc-pass}"
umask 077
python3 -c 'import secrets; print(secrets.token_urlsafe(9)[:8])' > "$BROWSER_PASSWORD_PATH"
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
  -passwdfile "$BROWSER_PASSWORD_PATH" -quiet >/dev/null 2>&1 &
websockify --web=/usr/share/novnc 0.0.0.0:6080 127.0.0.1:5900 >/dev/null 2>&1 &
echo "SIGMA Personal browser: VNC relay launched; starting Chromium"
# Keep Chromium's user namespace + seccomp renderer sandbox enabled.
# The Docker service grants only the namespace syscalls required by Chromium.
# Never add --no-sandbox: the process must fail closed on unsupported hosts.
# Use an app window in both real and synthetic modes: no Chromium tabs,
# address bar, or popup. The local worker's / route redirects straight to
# OpenAI authorization only when the account actually needs it.
# Suppress *conditional WebAuthn autofill UI* in this disposable Chromium
# profile. It is responsible for the native "Use passkey from another device"
# suggestion over Google's email field. This does NOT disable explicit WebAuthn
# prompts used for MFA/security keys. Keep the existing password-save/passkey-
# upgrade protections; never alter Google's sign-in page or injected JS.
exec /usr/bin/chromium --no-first-run --no-default-browser-check \
  --disable-dev-shm-usage --disable-extensions --password-store=basic \
  --disable-save-password-bubble \
  --enable-features=WebAuthnUsePasskeyFromAnotherDeviceInContextMenu \
  --disable-features=WebAuthenticationConditionalUI,AutofillReintroduceHybridPasskeyDropdownItem,WebAuthnPasskeyUpgrade,WebAuthnAmbientSignin \
  --user-data-dir="$BROWSER_PROFILE" --window-size=1280,800 \
  --app=http://127.0.0.1:8001/
