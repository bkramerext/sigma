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
from uuid import uuid4

from sigma.projects import ProjectError

LEASE_TIMEOUT_SECONDS = 45
DIRECTORY = ".sigma-browser-viewers"


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
