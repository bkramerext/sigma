# Reproducible Linux/amd64 image for the localhost OAuth viability experiment.
# This image is deliberately not the research Python/Sage sandbox.
FROM ghcr.io/astral-sh/uv:0.12.17@sha256:1194b357d63b7bea6c121d8eef5d08d29c26ffbcfc64ec5ebcefd642ea759edb AS uv
FROM python:3.12.8-slim@sha256:2199a62885a12290dc9c5be3ca0681d367576ab7bf037da120e564723292a2f0

ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HOME=/tmp DISPLAY=:99 \
    SIGMA_AUTH_HOME=/var/lib/sigma-poc-auth \
    PYTHONPATH=/opt/sigma/auth-poc:/opt/sigma/src

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium xvfb x11vnc novnc websockify ca-certificates fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
COPY --from=uv /uv /uvx /usr/local/bin/
WORKDIR /opt/sigma
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY samples ./samples
RUN uv sync --locked --no-dev
COPY auth-poc /opt/sigma/auth-poc
RUN mkdir -p /var/lib/sigma-poc-auth /tmp/chromium \
    && chmod 0700 /var/lib/sigma-poc-auth \
    && chown -R 10001:10001 /var/lib/sigma-poc-auth /tmp/chromium
USER 10001:10001
EXPOSE 6080
ENTRYPOINT ["/bin/sh", "/opt/sigma/auth-poc/boot.sh"]
