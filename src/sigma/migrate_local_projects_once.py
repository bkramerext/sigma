"""TEMPORARY: one-time transfer of original local projects into the Google owner's workspace.

Delete this module after the zetacontinuation@gmail.com migration is verified
(see issue #702). Nothing in normal Saved/Recent or project ACLs uses the old index.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import zlib
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


_FROZEN_SNAPSHOT = re.compile(
    r"^((?:artifacts/papers/snapshots|papers/\.snapshots)/)([0-9a-f]{64})(\.json\.zlib)$"
)
_MAX_FROZEN_BYTES = 128 * 1024 * 1024


def _relocate_members(
    members: dict[str, bytes], source: Path, destination: Path, project_id: str
) -> dict[str, bytes]:
    """Rebind path-owned records without rekeying project/session/evidence IDs.

    Only temporary migration code uses this; the ordinary copy operation
    intentionally creates a distinct project and cannot be reused here.
    """
    from sigma.project_copy import _canonical, _encode, _rewrite

    old_path, new_path = str(source.resolve()), str(destination.resolve())
    historical_paths = {old_path}
    for name, raw in members.items():
        if not (name.startswith("research-sessions/") and name.endswith(".json")):
            continue
        try:
            record = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(record, dict) and record.get("project_id") == project_id:
            recorded_path = record.get("project_path")
            if isinstance(recorded_path, str) and recorded_path.startswith("/"):
                historical_paths.add(recorded_path)
    substitutions = {
        path: new_path
        for path in sorted(historical_paths, key=len, reverse=True)
        if path != new_path
    }

    rewritten: dict[str, bytes] = {}
    digest_map: dict[str, str] = {}
    for name, raw in members.items():
        match = _FROZEN_SNAPSHOT.fullmatch(name)
        if match is None:
            rewritten[name] = raw
            continue
        old_digest = match.group(2)
        try:
            inflated = zlib.decompressobj()
            expanded = inflated.decompress(raw, _MAX_FROZEN_BYTES + 1)
            if len(expanded) > _MAX_FROZEN_BYTES or not inflated.eof or inflated.unused_data:
                raise ValueError("Invalid frozen evidence")
            expanded += inflated.flush()
            if hashlib.sha256(expanded).hexdigest() != old_digest:
                raise ValueError("Frozen evidence checksum changed")
            record = json.loads(expanded)
            updated = _rewrite(record, substitutions)
            if updated == record:
                rewritten[name] = raw
                continue
            packed = _canonical(updated)
            new_digest = hashlib.sha256(packed).hexdigest()
            target = match.group(1) + new_digest + match.group(3)
            if target in rewritten:
                raise ValueError("Relocated frozen evidence name collision")
            digest_map[old_digest] = new_digest
            rewritten[target] = zlib.compress(packed, level=6)
        except (ValueError, UnicodeDecodeError, zlib.error) as exc:
            raise ProjectError(f"Cannot relocate frozen evidence {name}: {exc}") from exc

    result: dict[str, bytes] = {}
    for name, raw in rewritten.items():
        if not name.endswith(".json"):
            result[name] = raw
            continue
        try:
            record = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            if any(path.encode() in raw for path in substitutions):
                raise ProjectError(f"Unreadable JSON contains project path: {name}") from None
            result[name] = raw
            continue
        updated = _rewrite(_rewrite(record, substitutions), digest_map)
        if isinstance(updated, dict):
            for field in ("snapshot", "frozen_package"):
                package = updated.get(field)
                if isinstance(package, dict) and package.get("schema") == "sigma-paper-evidence-v2":
                    updated["snapshot_sha256"] = hashlib.sha256(_canonical(package)).hexdigest()
            if (
                name.startswith("research-sessions/")
                and updated.get("project_id") == project_id
                and "project_path" in updated
                and updated["project_path"] != new_path
            ):
                raise ProjectError(f"Research session path did not migrate: {name}")
        result[name] = _encode(updated) if updated != record else raw
    return result


def _relocate_staged(source: Path, destination: Path, staged: Path, project_id: str) -> None:
    """Transform only path-dependent records in the private staging copy."""
    if staged.is_file():
        from sigma.project_bundle import _decode, stored_bundle

        members = _decode(json.loads(staged.read_bytes()))
        rewritten = _relocate_members(members, source, destination, project_id)
        if rewritten != members:
            staged.write_text(
                json.dumps(stored_bundle(rewritten), sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
        return

    members: dict[str, bytes] = {}
    for file in staged.rglob("*"):
        if file.is_file() and (file.name.endswith(".json") or file.name.endswith(".json.zlib")):
            members[file.relative_to(staged).as_posix()] = file.read_bytes()
    changed = _relocate_members(members, source, destination, project_id)
    for removed in members.keys() - changed.keys():
        (staged / removed).unlink()
    for name, raw in changed.items():
        if members.get(name) != raw:
            path = staged / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)


def _copy_verified(source: Path, destination: Path) -> None:
    """Copy/rebind in staging; compare fingerprints before any publication."""
    project_id, _ = _metadata(source)
    original = _fingerprint(source)
    with tempfile.TemporaryDirectory(prefix=".sigma-migrate-", dir=destination.parent) as temp:
        staged = Path(temp) / destination.name
        if source.is_dir():
            shutil.copytree(source, staged, symlinks=True)
        else:
            shutil.copy2(source, staged, follow_symlinks=False)
        if _fingerprint(source) != original or _fingerprint(staged) != original:
            raise ProjectError(f"Project changed during migration: {source}")
        _relocate_staged(source, destination, staged, project_id)
        relocated = _fingerprint(staged)
        if _fingerprint(source) != original:
            raise ProjectError(f"Project changed while rebasing paths: {source}")
        # Retries validate an already published copy without ever overwriting it.
        if destination.exists():
            if _fingerprint(destination) != relocated:
                raise ProjectError(f"Migration destination differs from original: {destination}")
            return
        staged.rename(destination)
        if _fingerprint(destination) != relocated:
            raise ProjectError(f"Relocated project did not verify: {destination}")


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
        or principal.role == "guest"
        or principal.subject.startswith(("mock:", "local-admin:"))
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
