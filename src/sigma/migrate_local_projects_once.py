"""TEMPORARY: one-time transfer of original local projects into the Google owner's workspace.

Delete this module after the zetacontinuation@gmail.com migration is verified
(see issue #702). Nothing in normal Saved/Recent or project ACLs uses the old index.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path

from sigma import cloud_auth, cloud_workspaces
from sigma.projects import ProjectError, _decode, local_projects_root

TARGET_EMAIL = "zetacontinuation@gmail.com"
_MARKER = ".sigma-state/local-projects-migrated-v1.json"


def _metadata(path: Path) -> tuple[str, str]:
    """Validate a project without requiring permission to open the old workspace."""
    from sigma.project_bundle import read_file

    if path.is_symlink():
        raise ProjectError(f"Cannot migrate symbolic-link project: {path}")
    if path.suffix == ".json" and path.is_file():
        payload = read_file(path, "project.json")
    elif path.suffix == ".sigma" and path.is_dir():
        source = path / "project.json"
        if source.is_symlink() or not source.is_file():
            raise ProjectError(f"Cannot migrate invalid project: {path}")
        payload = source.read_bytes()
    else:
        raise ProjectError(f"Cannot migrate invalid project: {path}")
    document = _decode(json.loads(payload))
    return document.id, document.title


def _fingerprint(source: Path) -> str:
    """Hash every byte, rejecting links and special files before copying."""
    digest = hashlib.sha256()
    paths = [source] if source.is_file() else sorted(source.rglob("*"))
    for path in paths:
        relative = path.relative_to(source).as_posix() if path != source else "project"
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise ProjectError(f"Cannot migrate symbolic-link project member: {path}")
        if stat.S_ISDIR(info.st_mode):
            digest.update(("D:" + relative).encode())
            continue
        if not stat.S_ISREG(info.st_mode):
            raise ProjectError(f"Cannot migrate special project member: {path}")
        digest.update(("F:" + relative + ":" + str(info.st_size)).encode())
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def _copy_verified(source: Path, destination: Path) -> None:
    """No overwrite. Retain the source untouched until copy verification completes."""
    original = _fingerprint(source)
    if destination.exists():
        if _fingerprint(destination) != original:
            raise ProjectError(f"Migration destination differs from original: {destination}")
        return
    with tempfile.TemporaryDirectory(prefix=".sigma-migrate-", dir=destination.parent) as temp:
        staged = Path(temp) / destination.name
        if source.is_dir():
            shutil.copytree(source, staged, symlinks=True)
        else:
            shutil.copy2(source, staged, follow_symlinks=False)
        if _fingerprint(source) != original or _fingerprint(staged) != original:
            raise ProjectError(f"Project changed during migration: {source}")
        # The workspace is private; never replace an existing project.
        if destination.exists():
            if _fingerprint(destination) != original:
                raise ProjectError(f"Migration destination already exists: {destination}")
            return
        staged.rename(destination)


def _source_inventory() -> tuple[dict, list[tuple[Path, str, str]]]:
    """Read old local state only during this one-time transfer."""
    from sigma import recents

    with cloud_workspaces.without_workspace(), recents._index() as saved:
        index = {
            "entries": [dict(entry) for entry in saved["entries"]],
            "pins": dict(recents._effective_pins(saved)),
            "dismissed_default_pins": list(saved.get("dismissed_default_pins", [])),
        }

    paths = [Path(entry["path"]) for entry in index["entries"]]
    saved_paths = {path.absolute() for path in paths}
    root = local_projects_root()
    paths.extend(
        sorted(
            path
            for path in root.iterdir()
            if (path.suffix == ".json" and path.is_file())
            or (path.suffix == ".sigma" and path.is_dir())
        )
    )
    seen: dict[str, Path] = {}
    inventory: list[tuple[Path, str, str]] = []
    for path in paths:
        original = path.absolute()
        try:
            project_id, title = _metadata(original)
        except (ProjectError, OSError, ValueError, KeyError, TypeError):
            if original in saved_paths:
                raise  # A Saved project must never silently disappear.
            continue  # The project root also contains non-project JSON metadata.
        if project_id in seen:
            if seen[project_id] != original:
                raise ProjectError(f"Duplicate project identity in migration: {project_id}")
            continue
        seen[project_id] = original
        inventory.append((original, project_id, title))
    return index, inventory


def migrate_if_needed(principal: cloud_auth.Principal) -> None:
    """Run once for the verified target user, then remove this code in #702."""
    workspace = cloud_workspaces.current()
    config = cloud_auth.config()
    if (
        workspace is None
        or workspace.guest
        or not config.local
        or principal.email.casefold() != TARGET_EMAIL
        or principal.subject != workspace.verified_subject
    ):
        return

    marker = workspace.path / _MARKER
    if marker.is_file():
        return

    from sigma import project_collaboration, recents

    lock_file = workspace.path / ".sigma-local-migration.lock"
    fd = os.open(lock_file, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        if marker.is_file():
            return

        original_index, inventory = _source_inventory()
        destinations: dict[str, str] = {}
        for source, project_id, _title in inventory:
            destination = workspace.path / source.name
            if destination.exists():
                try:
                    existing_id, _ = _metadata(destination)
                except (OSError, ValueError, ProjectError):
                    existing_id = ""
                if existing_id != project_id:
                    digest = hashlib.sha256(str(source).encode()).hexdigest()[:12]
                    destination = workspace.path / f"{source.stem}-imported-{digest}{source.suffix}"
            _copy_verified(source, destination)
            copied_id, _ = _metadata(destination)
            if copied_id != project_id:
                raise ProjectError(f"Copied project identity differs: {source}")
            destinations[project_id] = str(destination)
            # Grant ownership through the normal collaboration registry.
            from sigma.projects import inspect_project

            project_collaboration.register_owner(inspect_project(destination))

        with recents._index() as index:
            # Keep the old Saved order and pins, without dropping projects that
            # were already created in the new workspace.
            imported = [
                {**entry, "path": destinations[entry["id"]]} for entry in original_index["entries"]
            ]
            imported_ids = {row["id"] for row in imported}
            existing = [
                {**entry, "path": destinations.get(entry["id"], entry["path"])}
                for entry in index["entries"]
                if entry["id"] not in imported_ids
            ]
            indexed = {row["id"] for row in imported + existing}
            for _source, project_id, _title in inventory:
                if project_id not in indexed:
                    from datetime import UTC, datetime

                    existing.append(
                        {
                            "id": project_id,
                            "path": destinations[project_id],
                            "accessed_at": datetime.now(UTC).isoformat(),
                            "included_example": False,
                        }
                    )
                    indexed.add(project_id)
            index["entries"] = imported + existing
            index["pins"] = {**index["pins"], **original_index["pins"]}
            index["dismissed_default_pins"] = sorted(
                set(index["dismissed_default_pins"]) | set(original_index["dismissed_default_pins"])
            )

        # Publish completion last. Until then retries verify, never overwrite.
        data = {"target": TARGET_EMAIL, "project_count": len(inventory), "version": 1}
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=marker.parent, prefix=".migration-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.replace(temporary, marker)
        finally:
            temporary.unlink(missing_ok=True)
    finally:
        os.close(fd)
