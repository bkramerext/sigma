"""Validated storage-mode configuration shared by all SIGMA entry points."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from sigma.ui_instance import private_directory


class StorageConfigurationError(RuntimeError):
    """Storage cannot safely serve the configured application mode."""


def backend() -> str:
    value = os.environ.get("SIGMA_STORAGE_BACKEND", "local").strip().casefold()
    if value not in {"local", "persistent_disk"}:
        raise StorageConfigurationError("SIGMA_STORAGE_BACKEND must be local or persistent_disk.")
    return value


def persistent_disk_enabled() -> bool:
    return backend() == "persistent_disk"


def storage_root(*, create: bool = True) -> Path | None:
    """Validate and return the private root; LOCAL mode has no shared root."""
    if not persistent_disk_enabled():
        return None
    configured = os.environ.get("SIGMA_STORAGE_ROOT", "").strip()
    if not configured:
        raise StorageConfigurationError("SIGMA_STORAGE_ROOT is required for persistent_disk.")
    candidate = Path(configured).expanduser()
    if not candidate.is_absolute() or candidate == Path(candidate.anchor):
        raise StorageConfigurationError("SIGMA_STORAGE_ROOT must be an absolute private directory.")
    try:
        from sigma.projects import ROOT

        if candidate.is_symlink():
            raise StorageConfigurationError("SIGMA_STORAGE_ROOT cannot be a symlink.")
        prospective = candidate.resolve(strict=False)
        project_root = (
            Path(os.environ.get("SIGMA_PROJECTS_ROOT", str(ROOT / "projects")))
            .expanduser()
            .resolve(strict=False)
        )
        repository = ROOT.resolve()
        if (
            prospective.is_relative_to(repository)
            or prospective.is_relative_to(project_root)
            or project_root.is_relative_to(prospective)
        ):
            raise StorageConfigurationError(
                "SIGMA_STORAGE_ROOT must be separate from the checkout and LOCAL project directory."
            )
        if not candidate.exists():
            if not create:
                raise StorageConfigurationError("SIGMA_STORAGE_ROOT is unavailable.")
            parent = candidate.parent
            parent_info = parent.lstat()
            if (
                not stat.S_ISDIR(parent_info.st_mode)
                or parent_info.st_uid != os.geteuid()
                or parent_info.st_mode & 0o077
            ):
                raise StorageConfigurationError(
                    "SIGMA_STORAGE_ROOT parent must be owned and private."
                )
            candidate.mkdir(mode=0o700)
        private_directory(candidate)
        resolved = candidate.resolve(strict=True)
        info = resolved.lstat()
        if info.st_uid != os.geteuid() or info.st_mode & 0o077 or not stat.S_ISDIR(info.st_mode):
            raise StorageConfigurationError("SIGMA_STORAGE_ROOT must be owned and mode 0700.")
        return resolved
    except StorageConfigurationError:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise StorageConfigurationError("SIGMA_STORAGE_ROOT is unavailable or unsafe.") from exc


def configure() -> Path | None:
    """Set safe defaults and validate that every persistent path is under the root."""
    root = storage_root()
    if root is None:
        return None
    derived = {
        "SIGMA_CLOUD_AUTH_HOME": root,
        "SIGMA_CLOUD_WORKSPACES_ROOT": root / "workspaces",
    }
    for name, expected in derived.items():
        supplied = os.environ.get(name, "").strip()
        path = Path(supplied).expanduser() if supplied else expected
        if not path.is_absolute() or path.is_symlink():
            raise StorageConfigurationError(
                f"{name} must be an absolute path inside SIGMA_STORAGE_ROOT."
            )
        try:
            resolved = path.resolve(strict=False)
            if not resolved.is_relative_to(root) or (
                name == "SIGMA_CLOUD_AUTH_HOME" and resolved != root
            ):
                raise StorageConfigurationError(f"{name} must resolve inside SIGMA_STORAGE_ROOT.")
            if name == "SIGMA_CLOUD_WORKSPACES_ROOT" and resolved != expected:
                raise StorageConfigurationError(
                    "SIGMA_CLOUD_WORKSPACES_ROOT must use the derived private workspace location."
                )
        except (OSError, RuntimeError, ValueError) as exc:
            raise StorageConfigurationError(f"{name} is unsafe.") from exc
        os.environ[name] = str(resolved)
    os.environ["SIGMA_CLOUD_AUTH_ENABLED"] = "true"
    return root


def validate_startup() -> None:
    if not persistent_disk_enabled():
        return
    configure()
    from sigma import cloud_auth

    config = cloud_auth.config()
    if not config.enabled or config.error or config.database is None:
        raise StorageConfigurationError(
            "persistent_disk requires ready authenticated workspace configuration."
        )
