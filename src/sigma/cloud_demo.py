"""Read-only hosted Demo backed by one explicitly configured audit snapshot."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

from sigma.projects import ProjectError, _decode


def _snapshot_path() -> Path:
    configured = os.environ.get("SIGMA_CLOUD_DEMO_AUDIT", "").strip()
    if not configured:
        raise ProjectError("The hosted Demo is not configured.")
    path = Path(configured).expanduser()
    if not path.is_absolute():
        raise ProjectError("The hosted Demo configuration is invalid.")
    try:
        resolved = path.resolve(strict=True)
        snapshot_info = resolved.stat()
        parent_info = resolved.parent.stat()
        if (
            not stat.S_ISREG(snapshot_info.st_mode)
            or snapshot_info.st_uid != os.geteuid()
            or snapshot_info.st_mode & 0o022
            or not stat.S_ISDIR(parent_info.st_mode)
            or parent_info.st_uid != os.geteuid()
            or parent_info.st_mode & 0o022
            or snapshot_info.st_size > 32 * 1024 * 1024
        ):
            raise ProjectError("The hosted Demo snapshot is unavailable.")
        private_roots = _private_workspace_roots()
        if any(resolved.is_relative_to(root) for root in private_roots):
            raise ProjectError("The hosted Demo snapshot is unavailable.")
        return resolved
    except (OSError, RuntimeError) as exc:
        raise ProjectError("The hosted Demo snapshot is unavailable.") from exc


def _private_workspace_roots() -> tuple[Path, ...]:
    """Resolve both Gate A workspace locations without creating private state."""
    roots: set[Path] = set()
    configured = os.environ.get("SIGMA_CLOUD_WORKSPACES_ROOT", "").strip()
    auth_home = os.environ.get("SIGMA_CLOUD_AUTH_HOME", "").strip()
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).expanduser())
    if auth_home:
        candidates.append(Path(auth_home).expanduser() / "workspaces")
    for candidate in candidates:
        if not candidate.is_absolute():
            raise ProjectError("The hosted Demo configuration is invalid.")
        try:
            roots.add(candidate.resolve(strict=False))
        except (OSError, RuntimeError, ValueError) as exc:
            raise ProjectError("The hosted Demo configuration is invalid.") from exc
    return tuple(roots)


def audit() -> dict[str, Any]:
    """Load the sole curated resource; callers cannot select a project or path."""
    path = _snapshot_path()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProjectError("The hosted Demo snapshot is unreadable.") from exc
    if (
        not isinstance(value, dict)
        or set(value) != {"export_version", "project", "agentic_runs", "research_sessions"}
        or value.get("export_version") != 2
        or not isinstance(value.get("agentic_runs"), list)
        or not isinstance(value.get("research_sessions"), list)
    ):
        raise ProjectError("The hosted Demo snapshot has an unsupported format.")
    try:
        project = _decode(value["project"])
    except (ProjectError, TypeError, ValueError, KeyError) as exc:
        raise ProjectError("The hosted Demo project is invalid.") from exc
    if not project.strategies or not value["research_sessions"]:
        raise ProjectError("The hosted Demo must include saved strategies and sessions.")
    return value


def report(output_format: str) -> tuple[str | bytes, str]:
    from sigma.project_reports import render_report

    try:
        return render_report(audit(), output_format)
    except ValueError as exc:
        raise ProjectError(str(exc)) from exc
