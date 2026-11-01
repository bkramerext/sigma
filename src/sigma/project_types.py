"""Canonical built-in catalog and private, durable custom project types."""

from __future__ import annotations

import base64
import binascii
import fcntl
import json
import os
import re
import stat
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from sigma.projects import ProjectError, projects_root

MAX_ICON_BYTES = 512_000
MAX_REFERENCES = 100
_BUILTIN_FILE = Path(__file__).with_name("data") / "builtin_project_types.json"
_DATA_URI = re.compile(r"^data:(image/(?:png|webp));base64,([A-Za-z0-9+/]+=*)$")


def placeholder_icon() -> dict[str, Any]:
    try:
        raw = json.loads(_BUILTIN_FILE.read_text(encoding="utf-8"))
        icon = raw["icons"]["placeholder"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("The placeholder project type icon is invalid") from exc
    return icon


@dataclass(frozen=True)
class ProjectType:
    id: str
    name: str
    scope: str
    user_defined: bool
    icon: dict[str, Any]
    based_on: str | None = None
    origin: str | None = None
    research_standards_references: tuple[str, ...] = ()
    publication_standards_references: tuple[str, ...] = ()
    behavior: dict[str, bool] | None = None

    def record(self) -> dict[str, Any]:
        result = dict(self.__dict__)
        result["research_standards_references"] = list(self.research_standards_references)
        result["publication_standards_references"] = list(self.publication_standards_references)
        result["icon"] = self.icon
        result["behavior"] = dict(self.behavior or {})
        return result


def _validate_references(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > MAX_REFERENCES:
        raise ProjectError(f"{field} must be a list of at most {MAX_REFERENCES} URLs")
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str) or len(item) > 2048:
            raise ProjectError(f"{field} contains an invalid URL")
        from urllib.parse import urlsplit, urlunsplit

        try:
            parsed = urlsplit(item.strip())
            hostname = parsed.hostname
            port = parsed.port
        except ValueError as exc:
            raise ProjectError(f"{field} contains an invalid URL") from exc
        if parsed.scheme not in {"http", "https"} or not hostname or parsed.username:
            raise ProjectError(f"{field} URLs must use HTTP or HTTPS and include a host")
        host = hostname.casefold()
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        if (
            port is not None
            and not (parsed.scheme.casefold() == "https" and port == 443)
            and not (parsed.scheme.casefold() == "http" and port == 80)
        ):
            host += f":{port}"
        normalized = urlunsplit(
            (parsed.scheme.casefold(), host, parsed.path or "/", parsed.query, "")
        )
        key = normalized.casefold()
        if key in {entry.casefold() for entry in cleaned}:
            raise ProjectError(f"{field} cannot contain duplicate URLs")
        cleaned.append(normalized)
    return tuple(sorted(cleaned, key=str.casefold))


def _validate_icon(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProjectError("An icon is required")
    if value.get("kind") == "builtin" and value.get("key") == "placeholder":
        return placeholder_icon()
    if value.get("kind") == "builtin" and value.get("key"):
        try:
            catalog = json.loads(_BUILTIN_FILE.read_text(encoding="utf-8"))
            canonical = next(
                item["icon"]
                for item in catalog["project_types"]
                if item["id"] == value["key"] and item["icon"].get("kind") == "builtin"
            )
        except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
            raise ProjectError("Built-in icon reference is invalid") from exc
        return canonical
    match = _DATA_URI.fullmatch(str(value.get("data_uri", "")))
    if not match:
        raise ProjectError("Icon must be a PNG or WebP data URI")
    try:
        content = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ProjectError("Icon data is invalid") from exc
    if not content or len(content) > MAX_ICON_BYTES:
        raise ProjectError("Icon must be non-empty and at most 512 KB")
    mime = match.group(1)
    valid_bytes = (
        content.startswith(b"\x89PNG\r\n\x1a\n")
        if mime == "image/png"
        else content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    )
    if not valid_bytes:
        raise ProjectError("Icon bytes do not match their media type")
    return {"kind": "data", "data_uri": str(value["data_uri"])}


def _from_record(raw: dict[str, Any]) -> ProjectType:
    name = _required_text(raw.get("name"), "Name", 80)
    scope = _required_text(raw.get("scope"), "Scope", 500)
    return ProjectType(
        id=str(raw["id"]),
        name=name,
        scope=scope,
        user_defined=bool(raw.get("user_defined")),
        based_on=raw.get("based_on"),
        origin=raw.get("origin"),
        icon=_validate_icon(raw.get("icon")),
        research_standards_references=_validate_references(
            raw.get("research_standards_references", []), "Research references"
        ),
        publication_standards_references=_validate_references(
            raw.get("publication_standards_references", []), "Publication references"
        ),
        behavior=raw.get("behavior", {}) if not raw.get("user_defined") else {},
    )


def _required_text(value: Any, label: str, limit: int) -> str:
    if not isinstance(value, str):
        raise ProjectError(f"{label} is required")
    value = unicodedata.normalize("NFKC", value).strip()
    if not value or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ProjectError(f"{label} must contain 1–{limit} usable characters")
    return value


def _optional_text(value: Any, label: str, limit: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ProjectError(f"{label} must be text")
    value = unicodedata.normalize("NFKC", value).strip()
    if len(value) > limit or any(ord(c) < 32 for c in value):
        raise ProjectError(f"{label} must be at most {limit} usable characters")
    return value


def builtin_types() -> list[ProjectType]:
    try:
        raw = json.loads(_BUILTIN_FILE.read_text(encoding="utf-8"))
        records = raw["project_types"]
        result = [_from_record(record) for record in records]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("The built-in project type catalog is invalid") from exc
    return sorted(result, key=lambda item: item.name.casefold())


def _store_path() -> Path:
    return projects_root() / ".sigma-project-types.json"


def custom_types() -> list[ProjectType]:
    path = _store_path()
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise ProjectError("Custom project type storage is unsafe or unavailable") from exc
    try:
        with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_mode & 0o077
                or info.st_size > 16_000_000
            ):
                raise ProjectError("Custom project type storage is unsafe")
            raw = json.load(stream)
    except (OSError, ValueError, UnicodeError) as exc:
        raise ProjectError("Custom project type storage could not be read") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ProjectError("Custom project type storage has an unsupported format")
    records = raw.get("project_types")
    if not isinstance(records, list):
        raise ProjectError("Custom project type storage is invalid")
    result = [_from_record(item) for item in records if isinstance(item, dict)]
    return sorted(result, key=lambda item: item.name.casefold())


def all_types() -> list[ProjectType]:
    return [*builtin_types(), *custom_types()]


def catalog_revision() -> str:
    import hashlib

    path = _store_path()
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return hashlib.sha256(b"sigma-project-types-empty-v1").hexdigest()
    except OSError as exc:
        raise ProjectError("Custom project type storage is unsafe or unavailable") from exc
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or info.st_size > 16_000_000
        ):
            raise ProjectError("Custom project type storage is unsafe")
        return hashlib.sha256(stream.read(16_000_001)).hexdigest()


def project_usage(identifier: str) -> int:
    from sigma.projects import inspect_project

    count = 0
    try:
        entries = list(projects_root().iterdir())
    except OSError as exc:
        raise ProjectError("Project storage could not be inspected safely") from exc
    for path in entries:
        if path.name.startswith(".") or path.suffix not in {".sigma", ".json"}:
            continue
        try:
            project = inspect_project(path).project
        except (ProjectError, OSError, ValueError):
            continue
        if project.investigation_type == identifier:
            count += 1
    return count


def get_type(identifier: str) -> ProjectType | None:
    return next((item for item in all_types() if item.id == identifier), None)


def safe_project_snapshot(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if not isinstance(value.get("name"), str) or not value["name"].strip():
        return False
    if not isinstance(value.get("scope"), str) or not value["scope"].strip():
        return False
    if not isinstance(value.get("user_defined"), bool):
        return False
    try:
        _validate_icon(value.get("icon"))
        _validate_references(value.get("research_standards_references"), "Research references")
        _validate_references(
            value.get("publication_standards_references"), "Publication references"
        )
    except ProjectError:
        return False
    behavior = value.get("behavior")
    return isinstance(behavior, dict) and all(type(flag) is bool for flag in behavior.values())


def normalize_project_snapshot(value: Any, identifier: str) -> dict[str, Any] | None:
    if not safe_project_snapshot(value) or value.get("id") != identifier:
        return None
    try:
        return {
            "id": identifier,
            "name": _required_text(value["name"], "Name", 80),
            "scope": _required_text(value["scope"], "Scope", 500),
            "user_defined": value["user_defined"],
            "based_on": value.get("based_on"),
            "origin": value.get("origin"),
            "icon": _validate_icon(value.get("icon")),
            "research_standards_references": list(
                _validate_references(value["research_standards_references"], "Research references")
            ),
            "publication_standards_references": list(
                _validate_references(
                    value["publication_standards_references"], "Publication references"
                )
            ),
            "behavior": {
                key: flag
                for key, flag in value["behavior"].items()
                if key in {"mathematical", "lean"}
            },
        }
    except (ProjectError, KeyError, TypeError):
        return None


def _write_custom(items: list[ProjectType], *, expected_revision: str | None = None) -> None:
    path = _store_path()
    document = {"schema_version": 1, "project_types": [item.record() for item in items]}
    payload = json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if len(payload.encode("utf-8")) > 16_000_000:
        raise ProjectError("Custom project type catalog exceeds the storage limit")
    lock_fd = os.open(
        path.parent / ".sigma-project-types.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(lock_fd, "rb") as lock:
        lock_info = os.fstat(lock.fileno())
        if (
            not stat.S_ISREG(lock_info.st_mode)
            or lock_info.st_uid != os.getuid()
            or lock_info.st_mode & 0o077
        ):
            raise ProjectError("Custom project type lock is unsafe")
        fcntl.flock(lock, fcntl.LOCK_EX)
        if expected_revision is not None and expected_revision != catalog_revision():
            raise ProjectError(
                "Project types changed in another window; reload and review before saving"
            )
        descriptor, temporary = tempfile.mkstemp(prefix=".project-types-", dir=path.parent)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        fcntl.flock(lock, fcntl.LOCK_UN)


def save_type(raw: dict[str, Any], *, identifier: str | None = None) -> ProjectType:
    if not isinstance(raw, dict):
        raise ProjectError("Project type must be an object")
    revision = catalog_revision()
    current = custom_types()
    if identifier and not any(item.id == identifier for item in current):
        raise ProjectError("Only an existing custom type can be edited")
    candidate_raw = dict(raw)
    candidate_raw["id"] = identifier or str(uuid4())
    candidate_raw["user_defined"] = True
    candidate_raw["behavior"] = {}
    candidate = _from_record(candidate_raw)
    folded = candidate.name.casefold()
    if any(item.id != candidate.id and item.name.casefold() == folded for item in all_types()):
        raise ProjectError("A project type with that name already exists")
    if candidate.based_on:
        base = get_type(candidate.based_on)
        if base is None:
            raise ProjectError("Choose an available base project type")
        candidate = ProjectType(
            **{
                **candidate.__dict__,
                "based_on": candidate.based_on,
                "origin": base.id,
            }
        )
    _write_custom(
        [*(item for item in current if item.id != candidate.id), candidate],
        expected_revision=revision,
    )
    return candidate


def remove_type(identifier: str, *, expected_revision: str | None = None) -> bool:
    revision = catalog_revision()
    if expected_revision is not None and expected_revision != revision:
        raise ProjectError(
            "Project types changed in another window; reload and review before removing"
        )
    current = custom_types()
    if not any(item.id == identifier for item in current):
        raise ProjectError("Only an existing custom type can be removed")
    _write_custom([item for item in current if item.id != identifier], expected_revision=revision)
    return True


def replace_custom_types(
    records: list[dict[str, Any]],
    *,
    expected_revision: str | None = None,
    confirmed_removals: dict[str, int] | None = None,
) -> list[ProjectType]:
    if len(records) > 500:
        raise ProjectError("Too many custom project types")
    builtins = builtin_types()
    builtin_ids = {item.id for item in builtins}
    old_items = custom_types()
    old_ids = {item.id for item in old_items}
    incoming_ids = {
        raw.get("id") for raw in records if isinstance(raw, dict) and isinstance(raw.get("id"), str)
    }
    removed_ids = old_ids - incoming_ids
    confirmed_removals = confirmed_removals or {}
    if set(confirmed_removals) != removed_ids:
        raise ProjectError("Review and confirm every custom project type removal before saving")
    for identifier in removed_ids:
        if confirmed_removals[identifier] != project_usage(identifier):
            raise ProjectError("Project references changed; review the removal warning again")
    result: list[ProjectType] = []
    seen_ids: set[str] = set()
    seen_names = {item.name.casefold() for item in builtins}
    for raw in records:
        if not isinstance(raw, dict) or raw.get("user_defined") is not True:
            raise ProjectError("Only custom project type records can be saved")
        item_id = raw.get("id")
        if not isinstance(item_id, str) or item_id in builtin_ids or item_id in seen_ids:
            raise ProjectError("Project type identity is invalid or duplicated")
        item = _from_record(raw)
        key = item.name.casefold()
        if key in seen_names:
            raise ProjectError("Project type names must be unique")
        parent_is_in_batch = item.based_on in incoming_ids
        parent_is_persisted = item.based_on is not None and get_type(item.based_on) is not None
        parent_is_retained_origin = item_id in old_ids
        if item.based_on and not (
            parent_is_in_batch or parent_is_persisted or parent_is_retained_origin
        ):
            # Existing derived types retain origin metadata after their parent is deleted.
            raise ProjectError("Choose an available base project type")
        seen_ids.add(item.id)
        seen_names.add(key)
        result.append(item)
    _write_custom(result, expected_revision=expected_revision)
    return sorted(result, key=lambda item: item.name.casefold())
