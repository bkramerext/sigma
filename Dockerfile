FROM ghcr.io/astral-sh/uv:0.12.17@sha256:1194b357d63b7bea6c121d8eef5d08d29c26ffbcfc64ec5ebcefd642ea759edb AS uv
FROM docker:27.5.1-cli@sha256:f56779b4e86550493153cc8642c9c8e40b5d934e43cb5b4ea463aea5245c5c01 AS docker-cli
FROM python:3.12.8-slim@sha256:2199a62885a12290dc9c5be3ca0681d367576ab7bf037da120e564723292a2f0 AS tectonic
# Preserve the upstream 0.15.0 version and sha256 pin on both CPU targets.
# BuildKit fetches both verified tarballs during this disposable build stage;
# only the correct executable enters the final image.
ADD --checksum=sha256:dfb82876f2986862996e564fa507a9e576e0c1e3bee63c2c1bd677c2543e6407 \
    https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.15.0/tectonic-0.15.0-x86_64-unknown-linux-musl.tar.gz \
    /tmp/tectonic-amd64.tar.gz
ADD --checksum=sha256:1f59f9fb8eb65e8ba18658fc9016767e7d3e12488ded8b8fffa34254e51ce42c \
    https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.15.0/tectonic-0.15.0-aarch64-unknown-linux-musl.tar.gz \
    /tmp/tectonic-arm64.tar.gz
ARG TARGETARCH
RUN set -eu; \
    case "$TARGETARCH" in \
      amd64) archive=/tmp/tectonic-amd64.tar.gz ;; \
      arm64) archive=/tmp/tectonic-arm64.tar.gz ;; \
      *) echo "Unsupported Tectonic architecture: $TARGETARCH" >&2; exit 1 ;; \
    esac; \
    tar -xzf "$archive" -C /usr/local/bin tectonic; \
    chmod 0755 /usr/local/bin/tectonic; \
    /usr/local/bin/tectonic --version; \
    rm /tmp/tectonic-amd64.tar.gz /tmp/tectonic-arm64.tar.gz
FROM python:3.12.8-slim@sha256:2199a62885a12290dc9c5be3ca0681d367576ab7bf037da120e564723292a2f0

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp

RUN apt-get update && apt-get install -y --no-install-recommends zstd \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=tectonic /usr/local/bin/tectonic /usr/local/bin/tectonic
WORKDIR /opt/sigma
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY samples ./samples
RUN uv sync --locked --no-dev --no-install-project \
    && uv sync --locked --no-dev \
    && mkdir -p /var/lib/sigma-auth /opt/sigma/demo \
    && chown -R 10001:10001 /var/lib/sigma-auth /opt/sigma/demo

# The curated snapshot is public read-only content, deliberately copied into the
# image rather than bind-mounted from the private mutable state volume.
COPY --chown=10001:10001 cloud-demo/handshake-demo-audit.json /opt/sigma/demo/handshake-demo-audit.json
RUN chmod 0444 /opt/sigma/demo/handshake-demo-audit.json \
    && chmod 0700 /var/lib/sigma-auth

ENV PATH=/opt/venv/bin:$PATH \
    SIGMA_RESEARCH_DOCKER_HOST=unix:///run/sigma-sandbox/docker.sock

USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-m", "sigma.deployment_health"]
CMD ["uvicorn", "sigma.server:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
