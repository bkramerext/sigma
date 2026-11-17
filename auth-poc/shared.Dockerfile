# One shared worker and disposable Chromium inside ONE Docker container.
# The two Linux UIDs are kept distinct despite sharing the Docker lifecycle.
# Install the pinned uv wheel *inside the target architecture*. The old
# ghcr.io/astral-sh/uv digest pointed at an amd64 binary; copying /uv from
# it into a native arm64 Chromium image failed with "uv: Exec format error".
FROM python:3.12.8-slim@sha256:2199a62885a12290dc9c5be3ca0681d367576ab7bf037da120e564723292a2f0
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_LINK_MODE=copy PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 PYTHONPATH=/opt/sigma/auth-poc:/opt/sigma/src \
    SIGMA_PERSONAL_SHARED_REAL_SIGNIN=1 SIGMA_PERSONAL_SHARED_VAULT=1 \
    SIGMA_CLOUD_AUTH_ENABLED=false \
    SIGMA_PERSONAL_SHARED_RECORDS=/var/lib/sigma-shared/records \
    SIGMA_PERSONAL_SHARED_WORKSPACES=/var/lib/sigma-shared/workspaces \
    SIGMA_PERSONAL_SHARED_KEY_FILE=/var/lib/sigma-shared-key/master \
    SIGMA_AUTH_HOME=/var/lib/sigma-shared/workspaces
RUN python -m pip install --no-cache-dir "uv==0.12.17" && uv --version
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium xvfb x11vnc novnc websockify ca-certificates fonts-liberation util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin sigma-personal \
    && useradd --uid 11001 --no-create-home --shell /usr/sbin/nologin sigma-browser \
    && mkdir -p /var/lib/sigma-shared/records \
       /var/lib/sigma-shared/workspaces /var/lib/sigma-shared-key \
    && chown -R 10001:10001 /var/lib/sigma-shared /var/lib/sigma-shared-key \
    && chmod 0700 /var/lib/sigma-shared/records /var/lib/sigma-shared/workspaces /var/lib/sigma-shared-key
# Disable Chromium password storage without restricting WebAuthn/passkeys.
# Do not disable PasswordManagerPasskeysEnabled or WebAuthenticationConditionalUI:
# they are needed for legitimate real ChatGPT passkey authentication.
RUN mkdir -p /etc/chromium/policies/managed \
    && printf '%s' '{"PasswordManagerEnabled":false}' \
       > /etc/chromium/policies/managed/sigma-no-password-saving.json
WORKDIR /opt/sigma
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY samples ./samples
RUN uv sync --locked --no-dev
COPY auth-poc /opt/sigma/auth-poc
RUN chmod -R a+rX /opt/sigma/auth-poc /opt/sigma/src /opt/sigma/samples \
    && /opt/venv/bin/python -c 'import cryptography; from sigma import chatgpt_auth'
EXPOSE 8001 6080
HEALTHCHECK --interval=20s --timeout=4s --start-period=30s --retries=3 \
    CMD /opt/venv/bin/python -c "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=3).status == 200"
ENTRYPOINT ["/opt/venv/bin/python", "/opt/sigma/auth-poc/shared_supervisor.py"]
