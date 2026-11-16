# Credential-holding OAuth worker. Chromium lives in a separate container.
FROM ghcr.io/astral-sh/uv:0.12.17@sha256:1194b357d63b7bea6c121d8eef5d08d29c26ffbcfc64ec5ebcefd642ea759edb AS uv
FROM python:3.12.8-slim@sha256:2199a62885a12290dc9c5be3ca0681d367576ab7bf037da120e564723292a2f0
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp \
    SIGMA_AUTH_HOME=/var/lib/sigma-poc-auth \
    PYTHONPATH=/opt/sigma/auth-poc:/opt/sigma/src
COPY --from=uv /uv /uvx /usr/local/bin/
WORKDIR /opt/sigma
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY samples ./samples
RUN uv sync --locked --no-dev
COPY auth-poc /opt/sigma/auth-poc
RUN chmod -R a+rX /opt/sigma/auth-poc /opt/sigma/src /opt/sigma/samples \
    && mkdir -p /var/lib/sigma-poc-auth && chmod 0700 /var/lib/sigma-poc-auth \
    && chown 10001:10001 /var/lib/sigma-poc-auth
USER 10001:10001
# The editable install imports from src at runtime. Check as the worker user.
RUN /opt/venv/bin/python -c 'from sigma import chat, chatgpt_auth'
# Intentionally NOT published: browser shares only our network namespace.
EXPOSE 8001
ENTRYPOINT ["/bin/sh", "/opt/sigma/auth-poc/worker_boot.sh"]
