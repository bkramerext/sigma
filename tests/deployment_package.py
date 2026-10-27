"""Offline checks for the pinned GCE Docker deployment package and secrets."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sigma import cloud_auth, cloud_runtime_check, deployment_health, openai_connection
from sigma.config_secrets import SecretConfigurationError, secret_value

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    backend = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    frontend = (ROOT / "deploy/frontend.Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "deploy/compose.yaml").read_text(encoding="utf-8")
    caddy = (ROOT / "deploy/Caddyfile").read_text(encoding="utf-8")
    host_caddy = (ROOT / "deploy/host-caddy.Caddyfile").read_text(encoding="utf-8")
    gce_compose = (ROOT / "deploy/compose.gce.yaml").read_text(encoding="utf-8")
    startup = (ROOT / "deploy/start-gce.sh").read_text(encoding="utf-8")
    release = (ROOT / "deploy/release_image.py").read_text(encoding="utf-8")
    systemd = (ROOT / "deploy/systemd/sigma.service").read_text(encoding="utf-8")

    for digest in (
        "2199a62885a12290dc9c5be3ca0681d367576ab7bf037da120e564723292a2f0",
        "1194b357d63b7bea6c121d8eef5d08d29c26ffbcfc64ec5ebcefd642ea759edb",
        "f56779b4e86550493153cc8642c9c8e40b5d934e43cb5b4ea463aea5245c5c01",
    ):
        assert f"@sha256:{digest}" in backend
    assert "uv sync --locked --no-dev" in backend
    assert "USER 10001:10001" in backend
    assert "--network=none" in (ROOT / "src/sigma/python_sandbox.py").read_text(encoding="utf-8")
    assert "npm --prefix frontend ci" in frontend and "package-lock.json" in frontend
    assert "COPY pyproject.toml ./pyproject.toml" in frontend
    assert "sigma-state:/var/lib/sigma-auth" in compose
    assert (
        "device: ${SIGMA_STATE_DISK_MOUNT:?set mounted persistent state disk}/auth" in gce_compose
    )
    assert "SIGMA_STORAGE_BACKEND: persistent_disk" in gce_compose
    assert "SIGMA_STORAGE_ROOT: /var/lib/sigma-auth" in gce_compose
    assert "ports: !override" in gce_compose
    assert '"127.0.0.1:18080:80/tcp"' in gce_compose
    assert "SIGMA_CADDY_SCHEME: http" in gce_compose
    assert "SIGMA_CADDY_UPSTREAM_SCHEME: https" in gce_compose
    assert "SIGMA_CLOUD_WORKSPACES_ROOT: /var/lib/sigma-auth/workspaces" in gce_compose
    assert "SIGMA_PROJECTS_ROOT" not in compose + gce_compose
    assert "SIGMA_CLOUD_OPENAI_API_KEY_FILE" in compose
    assert "SIGMA_CLOUD_SPONSORED_ENABLED: ${SIGMA_CLOUD_SPONSORED_ENABLED:-false}" in compose
    assert "SIGMA_RESEARCH_DOCKER_HOST" in compose
    assert "GOOGLE_OIDC_CLIENT_SECRET_FILE" in compose
    assert "SIGMA_CLOUD_AUTH_LOCAL" not in compose
    assert "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL" in compose
    assert "SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL" not in compose
    assert "SIGMA_SANDBOX_DOCKER_SOCKET" in compose
    assert cloud_runtime_check._require_rootless(["name=rootless"], False) is True
    assert cloud_runtime_check._require_rootless(["name=seccomp"], True) is False
    try:
        cloud_runtime_check._require_rootless(["name=seccomp"], False)
    except SystemExit as exc:
        assert "does not report rootless mode" in str(exc)
    else:
        raise AssertionError("Production runtime check accepted a non-rootless daemon")
    assert ":443/tcp" in compose and ":80/tcp" in compose
    assert ":443/udp" not in compose
    assert compose.count("    ports:") == 1
    assert "SIGMA_CADDY_SCHEME: ${SIGMA_CADDY_SCHEME:-https}" in compose
    assert "@api path /api /api/*" in caddy
    assert "handle @api" in caddy and "Strict-Transport-Security" in caddy
    assert '"8000:8000"' not in compose and '"5173:5173"' not in compose
    assert "reverse_proxy backend:8000" in caddy
    assert "reverse_proxy frontend:8080" in caddy
    assert "header_up X-Forwarded-Proto {$SIGMA_CADDY_UPSTREAM_SCHEME}" in caddy
    assert "sigma-research.duckdns.org" in host_caddy
    assert "reverse_proxy 127.0.0.1:18080" in host_caddy
    assert 'CMD ["python", "-m", "sigma.deployment_health"]' in backend
    assert "wget -q -O /dev/null http://127.0.0.1:8080/" in frontend
    assert "wget -q -O /dev/null http://127.0.0.1:2019/config/" in compose
    assert "depends_on:" in compose and "condition: service_healthy" in compose
    assert "Requires=docker.service sigma-sandbox.service" in systemd
    assert "After=docker.service sigma-sandbox.service" in systemd
    assert "RequiresMountsFor=/srv/sigma-state" in systemd
    assert 'mountpoint -q "$disk"' in startup
    assert "release_image.py verify" in startup and "up -d --no-build" in startup
    assert "org.opencontainers.image.revision" in release
    assert 'chown "${SIGMA_BACKEND_UID:-10001}:${SIGMA_BACKEND_GID:-10001}" "$disk/auth"' in startup
    assert 'chmod 0700 "$disk/auth"' in startup
    assert "gcloud" not in backend.lower() and "OPENAI_API_KEY=" not in compose

    # A disabled sponsor must not make the whole production stack unhealthy.
    with (
        patch.object(
            deployment_health.cloud_auth,
            "config",
            return_value=SimpleNamespace(enabled=True, error=None),
        ),
        patch.object(deployment_health.cloud_auth, "sponsored_access_enabled", return_value=False),
        patch("sigma.storage.validate_startup"),
        patch.object(
            deployment_health.openai_connection, "sponsored_auth_context", new_callable=AsyncMock
        ) as sponsor,
        patch.object(deployment_health.subprocess, "run") as docker_info,
    ):
        assert deployment_health.main() == 0
        sponsor.assert_not_called()
        docker_info.assert_called_once()

    with tempfile.TemporaryDirectory(prefix="sigma-secret-test-") as directory:
        path = Path(directory) / "secret"
        path.write_text("fixture-secret\n", encoding="utf-8")
        auth_root = Path(directory) / "auth"
        auth_root.mkdir(mode=0o700)
        cloud_environment = {
            "SIGMA_CLOUD_AUTH_ENABLED": "true",
            "SIGMA_CLOUD_AUTH_LOCAL": "false",
            "SIGMA_CLOUD_PUBLIC_ORIGIN": "https://sigma.example.test",
            "SIGMA_CLOUD_AUTH_HOME": str(auth_root),
            "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.test",
            "GOOGLE_OIDC_CLIENT_ID": "fixture.apps.googleusercontent.com",
            "GOOGLE_OIDC_CLIENT_SECRET_FILE": str(path),
            "SIGMA_CLOUD_OPENAI_API_KEY_FILE": str(path),
            "SIGMA_INVITATION_SMTP_USERNAME": "notify@example.test",
            "SIGMA_INVITATION_SMTP_PASSWORD_FILE": str(path),
        }
        with patch.dict(os.environ, cloud_environment, clear=True):
            assert cloud_auth.config().enabled and cloud_auth.config().error is None
            credential = asyncio.run(openai_connection.sponsored_auth_context("fixture-subject"))
            assert credential["identity"].startswith("cloud_service_api_key:")
            assert credential["token"] == "fixture-secret"
        with patch.dict(
            os.environ,
            {
                **cloud_environment,
                "GOOGLE_OIDC_CLIENT_SECRET": "ambiguous",
                "SIGMA_CLOUD_OPENAI_API_KEY": "ambiguous",
            },
            clear=True,
        ):
            assert cloud_auth.config().error is not None
            assert (
                asyncio.run(openai_connection.sponsored_auth_context("fixture-subject"))["identity"]
                == "cloud_unconfigured"
            )
        with patch.dict(os.environ, {"T42_TEST_SECRET_FILE": str(path)}, clear=False):
            os.environ.pop("T42_TEST_SECRET", None)
            assert secret_value("T42_TEST_SECRET") == "fixture-secret"
        with patch.dict(
            os.environ,
            {"T42_TEST_SECRET": "inline", "T42_TEST_SECRET_FILE": str(path)},
            clear=False,
        ):
            try:
                secret_value("T42_TEST_SECRET")
            except SecretConfigurationError:
                pass
            else:
                raise AssertionError("ambiguous inline and file secrets must fail closed")
        link = Path(directory) / "secret-link"
        link.symlink_to(path)
        with patch.dict(os.environ, {"T42_TEST_SECRET_FILE": str(link)}, clear=False):
            try:
                secret_value("T42_TEST_SECRET")
            except SecretConfigurationError:
                pass
            else:
                raise AssertionError("secret file symlinks must be rejected")
    print("Deployment package structure and secret-source checks passed.")


if __name__ == "__main__":
    main()
