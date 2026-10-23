FROM python:3.13-slim-bookworm@sha256:e32be0e55814a08977501ca863271d9bd02443710db8f2afaf8372e2c4508530

ENV UV_VERSION=0.12.17 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/app/.venv/bin:$PATH
WORKDIR /app
RUN pip install --no-cache-dir "uv==${UV_VERSION}"
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY cloud-demo ./cloud-demo
RUN uv sync --locked --no-dev --no-editable \
    && groupadd --gid 10001 sigma \
    && useradd --uid 10001 --gid sigma --home-dir /nonexistent --no-create-home sigma \
    && chown -R 10001:10001 /app/cloud-demo \
    && mkdir -p /var/lib/sigma \
    && chown 10001:10001 /var/lib/sigma
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=4s --start-period=20s --retries=3 \
  CMD ["/app/.venv/bin/python", "-m", "sigma.deployment", "healthcheck"]
CMD ["/app/.venv/bin/python", "-m", "sigma.deployment", "uvicorn", "sigma.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
