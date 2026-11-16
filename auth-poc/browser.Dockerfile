# Disposable browser-only image. No SIGMA source, tokens, or Docker socket.
FROM python:3.12.8-slim@sha256:2199a62885a12290dc9c5be3ca0681d367576ab7bf037da120e564723292a2f0
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp DISPLAY=:99
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium xvfb x11vnc novnc websockify ca-certificates fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
# Disable password-manager passkey creation in this disposable Chromium only.
# Existing passkey authentication remains available when required for MFA.
RUN mkdir -p /etc/chromium/policies/managed \
    && printf '%s\\n' '{"PasswordManagerPasskeysEnabled":false,"PasswordManagerEnabled":false}' \
      > /etc/chromium/policies/managed/sigma-no-passkeys.json \
    && chmod 0644 /etc/chromium/policies/managed/sigma-no-passkeys.json
COPY auth-poc/boot.sh /opt/sigma/boot.sh
COPY auth-poc/diag_probe.py /opt/sigma/diag_probe.py
RUN chmod 0755 /opt/sigma && chmod 0444 /opt/sigma/boot.sh /opt/sigma/diag_probe.py \
    && useradd --uid 11001 --no-create-home --shell /usr/sbin/nologin sandbox-browser
USER 11001:11001
# Check the entrypoint can traverse the directory and read the script.
RUN /bin/sh -n /opt/sigma/boot.sh
EXPOSE 6080
ENTRYPOINT ["/bin/sh", "/opt/sigma/boot.sh"]
