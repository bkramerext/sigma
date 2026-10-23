"""Fail-closed startup and health checks for the production container image."""

from __future__ import annotations

import os
import stat
import sys
import urllib.error
import urllib.request
from pathlib import Path

from sigma import cloud_auth, cloud_demo, cloud_workspaces

_VOLUME_MARKER = ".sigma-deployment-volume-v1"
_VOLUME_MARKER_CONTENT = b"SIGMA durable cloud data volume v1\n"


class DeploymentConfigurationError(RuntimeError):
    """Production deployment configuration or storage failed validation."""


def validate_production_configuration() -> dict[str, str]:
    """Check cloud auth, the mounted persistent volume, and the isolated Demo."""
    if os.environ.get("SIGMA_CLOUD_AUTH_ENABLED", "").strip().casefold() not in {
        "1",
        "true",
        "yes",
    }:
        raise DeploymentConfigurationError("Cloud authentication must be explicitly enabled.")

    configured_root = os.environ.get("SIGMA_PERSISTENT_DATA_ROOT", "").strip()
    if not configured_root:
        raise DeploymentConfigurationError("Persistent data storage is not configured.")
    root = Path(configured_root).expanduser()
    if not root.is_absolute():
        raise DeploymentConfigurationError("Persistent data storage is not configured safely.")
    try:
        root_info = root.lstat()
        if (
            not stat.S_ISDIR(root_info.st_mode)
            or stat.S_ISLNK(root_info.st_mode)
            or root_info.st_uid != os.geteuid()
            or root_info.st_mode & 0o077
        ):
            raise DeploymentConfigurationError("Persistent data storage is unavailable.")
        root = root.resolve(strict=True)
        marker = root / _VOLUME_MARKER
        marker_info = marker.lstat()
        if (
            not stat.S_ISREG(marker_info.st_mode)
            or stat.S_ISLNK(marker_info.st_mode)
            or marker_info.st_uid != os.geteuid()
            or marker_info.st_mode & 0o077
            or marker.read_bytes() != _VOLUME_MARKER_CONTENT
        ):
            raise DeploymentConfigurationError("Persistent data storage is unavailable.")
    except DeploymentConfigurationError:
        raise
    except OSError as exc:
        raise DeploymentConfigurationError("Persistent data storage is unavailable.") from exc

    cfg = cloud_auth.config()
    if not cfg.enabled or cfg.error or cfg.database is None or cfg.origin is None:
        raise DeploymentConfigurationError("Cloud authentication configuration is incomplete.")
    try:
        auth_home = Path(os.environ["SIGMA_CLOUD_AUTH_HOME"]).expanduser().resolve(strict=True)
        if not auth_home.is_relative_to(root) or not cfg.database.resolve(
            strict=True
        ).is_relative_to(root):
            raise DeploymentConfigurationError(
                "Authentication storage is outside persistent storage."
            )
        workspaces_root = cloud_workspaces.storage_root()
        if not workspaces_root.is_relative_to(root):
            raise DeploymentConfigurationError("Workspace storage is outside persistent storage.")
        snapshot = cloud_demo._snapshot_path()
        if snapshot.is_relative_to(root):
            raise DeploymentConfigurationError(
                "The public Demo must be separate from private storage."
            )
        probe = workspaces_root / f".sigma-storage-check-{os.getpid()}-{os.urandom(6).hex()}"
        fd = os.open(
            probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600
        )
        try:
            os.write(fd, b"ok")
            os.fsync(fd)
        finally:
            os.close(fd)
            probe.unlink()
    except DeploymentConfigurationError:
        raise
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        raise DeploymentConfigurationError(
            "Cloud storage or Demo configuration is unsafe."
        ) from exc

    return {
        "public_origin": cfg.origin,
        "data_root": str(root),
        "auth_database": str(cfg.database),
        "workspace_root": str(workspaces_root),
        "demo_snapshot": str(snapshot),
    }


def healthcheck() -> int:
    """Return a Docker-compatible status without logging identity or settings."""
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:8000/api/cloud-auth/status", timeout=2
        ) as response:
            import json

            body = json.load(response)
        return 0 if body.get("enabled") is True and body.get("ready") is True else 1
    except (OSError, urllib.error.URLError, ValueError):
        return 1


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "healthcheck":
        raise SystemExit(healthcheck())
    try:
        validate_production_configuration()
    except DeploymentConfigurationError:
        print("SIGMA production configuration or persistent storage is invalid.", file=sys.stderr)
        raise SystemExit(78) from None
    command = sys.argv[1:] or ["uvicorn", "sigma.api:app"]
    os.execvp(command[0], command)


if __name__ == "__main__":
    main()
