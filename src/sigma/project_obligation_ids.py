"""Project-wide, persistent compact identifiers for research obligations.

Each normalized obligation identity is mapped to a monotonically allocated
project-local alias (o1, o2, ...). The mapping is a project member, so JSON
exports and imports preserve it. Saved legacy 64-digit IDs are never rewritten.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from sigma.project_bundle import transform_members
from sigma.projects import ProjectError, _stage, project_path, project_write_lock

_MEMBER = "research-sessions/obligation-ids.json"


def _update(raw: bytes | None, identities: list[str]) -> tuple[bytes, dict[str, str]]:
    try:
        state = json.loads(raw) if raw is not None else {"next": 1, "by_digest": {}}
        next_value = state["next"]
        mapping = state["by_digest"]
        if (
            type(next_value) is not int
            or next_value < 1
            or not isinstance(mapping, dict)
            or any(
                not isinstance(key, str)
                or not re.fullmatch(r"[0-9a-f]{64}", key)
                or not isinstance(value, str)
                or not re.fullmatch(r"o[1-9][0-9]*", value)
                for key, value in mapping.items()
            )
            or len(set(mapping.values())) != len(mapping)
            or any(int(value[1:]) >= next_value for value in mapping.values())
        ):
            raise ValueError("Invalid obligation alias map")
    except (ValueError, TypeError, KeyError, UnicodeDecodeError) as exc:
        raise ProjectError("Project obligation ID allocation state is invalid") from exc
    for digest in dict.fromkeys(identities):
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ProjectError("Invalid obligation identity fingerprint")
        if digest not in mapping:
            mapping[digest] = f"o{next_value}"
            next_value += 1
    return (json.dumps({"next": next_value, "by_digest": mapping}, sort_keys=True) + "\n").encode(), {
        digest: mapping[digest] for digest in identities
    }


def assign_project_obligation_ids(path: str, digests: list[str]) -> dict[str, str]:
    """Allocate atomically for one project; repeated/concurrent calls reuse IDs."""
    if not digests:
        return {}
    project = project_path(path)
    if project.suffix == ".json":
        selected: dict[str, str] = {}

        def change(members: dict[str, bytes]) -> dict[str, bytes]:
            updated, assigned = _update(members.get(_MEMBER), digests)
            selected.update(assigned)
            return {_MEMBER: updated}

        transform_members(project, change)
        return selected

    directory = Path(project) / "research-sessions"
    if not directory.is_dir() or directory.is_symlink():
        raise ProjectError("Research session directory is unavailable")
    target = directory / "obligation-ids.json"
    with project_write_lock(project):
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ProjectError("Obligation ID state must be a regular file")
        try:
            raw = target.read_bytes() if target.exists() else None
        except OSError as exc:
            raise ProjectError("Cannot read obligation IDs") from exc
        updated, selected = _update(raw, digests)
        if raw != updated:
            staged = _stage(directory, updated)
            try:
                os.chmod(staged, 0o600)
                os.replace(staged, target)
            finally:
                staged.unlink(missing_ok=True)
        return selected
