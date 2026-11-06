"""Ephemeral browser-page leases keyed to canonical project storage locations.

Only *sessions explicitly started/resumed by the browser* require a viewer.
Standalone API/CLI sessions never inherit policy from earlier browser visits.
Lease files live outside portable project bundles and contain no user data.
"""

from __future__ import annotations

import hashlib
import os
import stat
import time
from pathlib import Path
from uuid import UUID, uuid4

from sigma.projects import ProjectError, projects_root

LEASE_TIMEOUT_SECONDS = 45
DIRECTORY = ".sigma-browser-viewers"
AUTH_HANDOFF_SECONDS = 15 * 60
AUTH_HANDOFF_MARKER = "auth-handoff.viewer"
WORKSPACE_PREFIX = "workspace-"


def _directory(root: Path) -> Path:
    folder = root / DIRECTORY
    if folder.is_symlink():
        raise ProjectError("Unsafe browser-presence directory")
    if folder.exists() and not folder.is_dir():
        raise ProjectError("Browser-presence path is not a directory")
    return folder


def _touch(path: Path) -> None:
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ProjectError("Browser-presence lease must be a regular file")
        os.utime(fd, None)
    finally:
        os.close(fd)


def _project_lease_location(path: str) -> tuple[Path, str]:
    """A copied/imported project keeps its ID but must not share leases."""
    from sigma.projects import inspect_project

    view = inspect_project(path)
    canonical = Path(view.path).resolve(strict=True)
    identity = hashlib.sha256(os.fsencode(canonical)).hexdigest()
    return _directory(canonical.parent), identity


def open_viewer(path: str) -> Path:
    """Register this browser page for one project storage path."""
    folder, identity = _project_lease_location(path)
    folder.mkdir(mode=0o700, exist_ok=True)
    folder = _directory(folder.parent)
    marker = folder / f"{identity}-{uuid4()}.viewer"
    _touch(marker)
    return marker


def touch_viewer(marker: Path) -> None:
    """Refresh a lease from the server, even if the browser tab is throttled."""
    if not marker.exists():
        raise ProjectError("Browser-presence lease disappeared")
    _touch(marker)


def close_viewer(marker: Path) -> None:
    marker.unlink(missing_ok=True)


def has_live_viewer(path: str) -> bool:
    """A browser stream for this exact project has a fresh lease.

    The caller decides *whether a viewer is required* using durable session
    metadata; this method deliberately has no historical-project exemption.
    """
    folder, identity = _project_lease_location(path)
    try:
        if _workspace_live_viewer(path):
            return True
    except ProjectError:
        # Background workers may have no request-local workspace context.
        # Preserve exact-project leases instead of failing the whole job.
        pass
    if not folder.exists():
        return False
    cutoff = time.time() - LEASE_TIMEOUT_SECONDS
    for marker in folder.glob(f"{identity}-*.viewer"):
        try:
            info = marker.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISREG(info.st_mode) and info.st_mtime >= cutoff:
            return True
    return False


def _workspace_lease_folder() -> Path:
    """The caller's authenticated workspace, not a global cross-user registry."""
    return _directory(projects_root().resolve(strict=True))


def open_workspace_viewer() -> Path:
    """Keep the owner's active jobs alive across project and home navigation."""
    folder = _workspace_lease_folder()
    folder.mkdir(mode=0o700, exist_ok=True)
    marker = folder / f"{WORKSPACE_PREFIX}{uuid4()}.viewer"
    _touch(marker)
    return marker


def refresh_workspace_viewer(viewer_id: str) -> None:
    """Renew a short workspace lease without holding an HTTP stream open."""
    try:
        identifier = str(UUID(viewer_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ProjectError("Invalid workspace viewer identifier") from exc
    folder = _workspace_lease_folder()
    folder.mkdir(mode=0o700, exist_ok=True)
    _touch(folder / f"{WORKSPACE_PREFIX}{identifier}.viewer")


def begin_auth_handoff() -> None:
    """Allow an explicit sign-out to reauthenticate without pausing in-flight jobs.

    This is a bounded 15-minute grace period, not generic disconnected-browser
    execution; tab closure or network loss cannot create the handoff.
    """
    folder = _workspace_lease_folder()
    folder.mkdir(mode=0o700, exist_ok=True)
    _touch(folder / AUTH_HANDOFF_MARKER)


def _workspace_live_viewer(path: str) -> bool:
    """Never allow a workspace lease to cover another identity's project."""
    from sigma.projects import inspect_project

    root = projects_root().resolve(strict=True)
    project = Path(inspect_project(path).path).resolve(strict=True)
    if not project.is_relative_to(root):
        return False
    folder = _workspace_lease_folder()
    if not folder.exists():
        return False
    now = time.time()
    for marker in folder.glob(f"{WORKSPACE_PREFIX}*.viewer"):
        try:
            info = marker.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISREG(info.st_mode) and info.st_mtime >= now - LEASE_TIMEOUT_SECONDS:
            return True
    marker = folder / AUTH_HANDOFF_MARKER
    try:
        info = marker.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISREG(info.st_mode) and info.st_mtime >= now - AUTH_HANDOFF_SECONDS
