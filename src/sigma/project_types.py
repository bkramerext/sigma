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
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from sigma.projects import ProjectError, projects_root

MAX_ICON_BYTES = 512_000
MAX_REFERENCES = 100
REFERENCE_FIELDS = ("research_standards_references", "publication_standards_references")
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
    research_standards_references: tuple[dict[str, str], ...] = ()
    publication_standards_references: tuple[dict[str, str], ...] = ()
    behavior: dict[str, bool] | None = None

    def record(self) -> dict[str, Any]:
        result = dict(self.__dict__)
        result["research_standards_references"] = list(self.research_standards_references)
        result["publication_standards_references"] = list(self.publication_standards_references)
        result["icon"] = self.icon
        result["behavior"] = dict(self.behavior or {})
        return result


def _validate_references(value: Any, field: str) -> tuple[dict[str, str], ...]:
    """Accept legacy URL strings or named records; persist canonical name + URL."""
    if not isinstance(value, list) or len(value) > MAX_REFERENCES:
        raise ProjectError(f"{field} must be a list of at most {MAX_REFERENCES} references")
    cleaned: dict[str, dict[str, str]] = {}
    from urllib.parse import urlsplit, urlunsplit

    for item in value:
        if isinstance(item, str):
            candidate, name = item.strip(), item.strip()
        elif isinstance(item, dict) and set(item) <= {"name", "url"}:
            candidate, name = item.get("url"), item.get("name")
            if not isinstance(candidate, str) or (name is not None and not isinstance(name, str)):
                raise ProjectError(f"{field} contains an invalid reference")
            candidate = candidate.strip()
            name = (name or candidate).strip()
        else:
            raise ProjectError(f"{field} contains an invalid reference")
        if not candidate:
            continue  # Blank editor rows disappear on Save.
        if len(candidate) > 2048:
            raise ProjectError(f"{field} contains an invalid URL")
        try:
            parsed = urlsplit(candidate)
            hostname, port = parsed.hostname, parsed.port
        except ValueError as exc:
            raise ProjectError(f"{field} contains an invalid URL") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not hostname
            or parsed.username
            or parsed.password
        ):
            raise ProjectError(f"{field} URLs must use HTTP or HTTPS and include a host")
        host = hostname.casefold()
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        if port is not None and not (
            (parsed.scheme.casefold() == "https" and port == 443)
            or (parsed.scheme.casefold() == "http" and port == 80)
        ):
            host += f":{port}"
        normalized = urlunsplit(
            (parsed.scheme.casefold(), host, parsed.path or "/", parsed.query, "")
        )
        # A URL may be longer than a human title; its fallback name is the URL.
        label = (
            normalized
            if not name or name == candidate
            else _optional_text(name, "Reference name", 240)
        )
        cleaned.setdefault(normalized, {"name": label, "url": normalized})
    return tuple(sorted(cleaned.values(), key=lambda ref: ref["url"].casefold()))


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


def common_research_references() -> tuple[dict[str, str], ...]:
    """Enabled shared research-method references; curated defaults stay immutable."""
    references = common_references()["research_standards_references"]
    disabled = set(
        reference_preferences().get("common", {}).get("research_standards_references", [])
    )
    return tuple(ref for ref in references if ref["url"] not in disabled)


def builtin_types() -> list[ProjectType]:
    try:
        raw = json.loads(_BUILTIN_FILE.read_text(encoding="utf-8"))
        records = raw["project_types"]
        result = [_from_record(record) for record in records]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("The built-in project type catalog is invalid") from exc
    return sorted(result, key=lambda item: item.name.casefold())


def _store_path() -> Path:
    """Use verified identity for private catalogs, even in shared-root local mode.

    Hosted workspaces retain their existing private catalog path. The legacy
    shared catalog is not silently attributed to a signed-in local account.
    """
    from sigma import cloud_auth, cloud_workspaces

    workspace = cloud_workspaces.current()
    if workspace is not None:
        return workspace.path / ".sigma-project-types.json"

    principal = cloud_auth.current_principal()
    if principal is None or not cloud_auth.config().enabled:
        # Single-user, anonymous local SIGMA and trusted offline tools retain
        # the established legacy path without migrating historical data.
        return projects_root() / ".sigma-project-types.json"
    if principal.role == "guest":
        raise ProjectError("Project type changes require member access")
    if not cloud_auth.config().local:
        raise ProjectError("Private project type workspace is unavailable")
    if (
        not isinstance(principal.subject, str)
        or not principal.subject
        or len(principal.subject) > 255
    ):
        raise ProjectError("Verified project type identity is unavailable")

    import hashlib

    from sigma.ui_instance import private_directory

    root = projects_root() / ".sigma-project-types-users"
    private_directory(root)
    # Domain-separated subject hash; never trust a browser ID, email, or path.
    subject_hash = hashlib.sha256(
        b"sigma-local-project-types-v1\0" + principal.subject.encode("utf-8")
    ).hexdigest()
    owner = root / subject_hash
    private_directory(owner)
    return owner / ".sigma-project-types.json"


def _read_catalog() -> dict[str, Any]:
    path = _store_path()
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return {"schema_version": 1, "project_types": []}
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
    if not isinstance(raw.get("project_types"), list):
        raise ProjectError("Custom project type storage is invalid")
    return raw


def custom_types() -> list[ProjectType]:
    records = _read_catalog()["project_types"]
    result = [_from_record(item) for item in records if isinstance(item, dict)]
    return sorted(result, key=lambda item: item.name.casefold())


def curated_common_references() -> dict[str, list[dict[str, str]]]:
    """Immutable curated defaults shared by every research discipline."""
    raw = json.loads(_BUILTIN_FILE.read_text(encoding="utf-8"))["common_references"]
    return {field: list(_validate_references(raw[field], field)) for field in REFERENCE_FIELDS}


def _validate_common_custom_references(value: Any) -> dict[str, list[dict[str, str]]]:
    if not isinstance(value, dict) or set(value) - set(REFERENCE_FIELDS):
        raise ProjectError("Common custom references must have research or publication categories")
    curated = curated_common_references()
    result: dict[str, list[dict[str, str]]] = {}
    for field in REFERENCE_FIELDS:
        refs = list(_validate_references(value.get(field, []), field))
        forbidden = {ref["url"] for ref in curated[field]}
        if any(ref["url"] in forbidden for ref in refs):
            raise ProjectError("Built-in common references cannot be replaced")
        result[field] = refs
    return result


def common_custom_references() -> dict[str, list[dict[str, str]]]:
    """Private user-created common guides, separate from built-in definitions."""
    return _validate_common_custom_references(_read_catalog().get("common_custom_references", {}))


def _validate_builtin_custom_references(value: Any) -> dict[str, dict[str, list[dict[str, str]]]]:
    """Validate private additions without permitting edits to curated built-in guides."""
    if not isinstance(value, dict):
        raise ProjectError("Built-in reference additions must be a map")
    curated = {item.id: item for item in builtin_types()}
    if set(value) - set(curated):
        raise ProjectError("Unknown built-in project type in reference additions")
    result: dict[str, dict[str, list[dict[str, str]]]] = {}
    for owner, fields in value.items():
        if not isinstance(fields, dict) or set(fields) - set(REFERENCE_FIELDS):
            raise ProjectError("Built-in additions must specify research or publication references")
        accepted: dict[str, list[dict[str, str]]] = {}
        for field in REFERENCE_FIELDS:
            references = list(_validate_references(fields.get(field, []), field))
            existing = {ref["url"] for ref in getattr(curated[owner], field)}
            if any(ref["url"] in existing for ref in references):
                raise ProjectError("Built-in project type references cannot be replaced")
            if references:
                accepted[field] = references
        if accepted:
            result[owner] = accepted
    return result


def builtin_custom_references() -> dict[str, dict[str, list[dict[str, str]]]]:
    """User-owned additions to built-in project types, stored separately from curated defaults."""
    return _validate_builtin_custom_references(_read_catalog().get("builtin_custom_references", {}))


def _definitions(
    custom: list[ProjectType] | None = None,
    builtin_additions: dict[str, dict[str, list[dict[str, str]]]] | None = None,
) -> dict[str, ProjectType]:
    """Merge reference overlays only for resolving effective types, not canonical records."""
    additions = builtin_custom_references() if builtin_additions is None else builtin_additions
    definitions = {}
    for item in builtin_types():
        fields = additions.get(item.id, {})
        definitions[item.id] = replace(
            item,
            **{
                field: (*getattr(item, field), *fields.get(field, [])) for field in REFERENCE_FIELDS
            },
        )
    definitions.update({item.id: item for item in (custom_types() if custom is None else custom)})
    return definitions


def common_references() -> dict[str, list[dict[str, str]]]:
    """Curated and user-created shared guides used by future work."""
    curated = curated_common_references()
    additions = common_custom_references()
    return {
        field: list({ref["url"]: ref for ref in [*curated[field], *additions[field]]}.values())
        for field in REFERENCE_FIELDS
    }


def _default_reference_preferences() -> dict[str, dict[str, list[str]]]:
    """New users start with every common and discipline-specific reference enabled.

    Preferences list *disabled* reference URLs; existing users retain their
    saved choices. No migration or propagation is performed.
    """
    return {}


def _validate_reference_preferences(
    value: Any,
    custom: list[ProjectType],
    *,
    drop_removed: bool = False,
    common_override: dict[str, list[dict[str, str]]] | None = None,
    builtin_override: dict[str, dict[str, list[dict[str, str]]]] | None = None,
) -> dict[str, dict[str, list[str]]]:
    """Validate disabled reference URLs against immutable and custom type definitions.

    Preference keys are type IDs (or "common"), then research/publication
    reference fields. No arbitrary URLs or modifications to built-ins are allowed.
    """
    if not isinstance(value, dict) or len(value) > 501:
        raise ProjectError("Reference preferences must be a map of project types")
    definitions = _definitions(custom, builtin_override)
    if "common" in definitions:
        raise ProjectError("Project type name 'common' is reserved for shared references")
    result: dict[str, dict[str, list[str]]] = {}
    for owner, fields in value.items():
        if not isinstance(owner, str) or not isinstance(fields, dict):
            raise ProjectError("Reference preferences contain an invalid project type")
        if owner == "common":
            allowed = common_override if common_override is not None else common_references()
        else:
            item = resolve_type_metadata(owner, definitions)
            if item is None:
                if drop_removed:
                    continue
                raise ProjectError("Reference preferences contain an unknown project type")
            allowed = {field: list(getattr(item, field)) for field in REFERENCE_FIELDS}
        if set(fields) - set(REFERENCE_FIELDS):
            raise ProjectError("Reference preferences contain an unknown category")
        chosen: dict[str, list[str]] = {}
        for field, urls in fields.items():
            if (
                not isinstance(urls, list)
                or len(urls) > MAX_REFERENCES
                or any(not isinstance(url, str) for url in urls)
            ):
                raise ProjectError("Disabled references must be a list of URLs")
            if len(set(urls)) != len(urls):
                raise ProjectError("Disabled references contain duplicate URLs")
            known = {ref["url"] for ref in allowed[field]}
            if not drop_removed and any(url not in known for url in urls):
                raise ProjectError("Only listed references may be disabled")
            kept = sorted((url for url in urls if url in known), key=str.casefold)
            if kept:
                chosen[field] = kept
        if chosen:
            result[owner] = chosen
    return result


def reference_preferences() -> dict[str, dict[str, list[str]]]:
    """Persisted, private presentation-independent reference usage switches."""
    catalog = _read_catalog()
    return _validate_reference_preferences(
        catalog.get("reference_preferences", _default_reference_preferences()), custom_types()
    )


def resolve_type_metadata(
    identifier: str, definitions: dict[str, ProjectType] | None = None
) -> ProjectType | None:
    """Resolve based_on transitively, preserving explicit child metadata.

    A child keeps its own name, scope, identity and saved icon/references. An
    uncustomized placeholder or empty reference list falls back recursively to
    the closest available ancestor. Missing parents use the child's snapshot;
    cycles are bounded and never followed indefinitely.
    """
    if definitions is None:
        definitions = _definitions()
    item = definitions.get(identifier)
    if item is None:
        return None
    ancestry: set[str] = {identifier}
    icon = item.icon
    research = list(item.research_standards_references)
    publication = list(item.publication_standards_references)
    parent_id = item.based_on
    while parent_id and parent_id not in ancestry:
        ancestry.add(parent_id)
        parent = definitions.get(parent_id)
        if parent is None:
            break
        if icon.get("key") == "placeholder" and parent.icon.get("key") != "placeholder":
            icon = parent.icon
        for target, field in (
            (research, parent.research_standards_references),
            (publication, parent.publication_standards_references),
        ):
            seen = {ref["url"] for ref in target}
            target.extend(ref for ref in field if ref["url"] not in seen)
        parent_id = parent.based_on
    return replace(
        item,
        icon=icon,
        research_standards_references=tuple(research),
        publication_standards_references=tuple(publication),
    )


def all_types() -> list[ProjectType]:
    definitions = _definitions()
    return [
        resolved
        for identifier in definitions
        if (resolved := resolve_type_metadata(identifier, definitions)) is not None
    ]


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
    """Snapshots carry effective shared and discipline-specific guidance."""
    item = next((row for row in all_types() if row.id == identifier), None)
    if item is None:
        return None
    common = common_references()
    preferences = reference_preferences()
    # Disabling a reference on a parent also applies to derived types.
    definitions = _definitions()
    ancestry = {identifier}
    ancestor = definitions[identifier].based_on
    while ancestor and ancestor not in ancestry and ancestor in definitions:
        ancestry.add(ancestor)
        ancestor = definitions[ancestor].based_on
    combined = {}
    for field in REFERENCE_FIELDS:
        disabled = set(preferences.get("common", {}).get(field, []))
        for ancestor_id in ancestry:
            disabled.update(preferences.get(ancestor_id, {}).get(field, []))
        by_url = {
            ref["url"]: ref
            for ref in [*common[field], *getattr(item, field)]
            if ref["url"] not in disabled
        }
        combined[field] = tuple(sorted(by_url.values(), key=lambda ref: ref["url"].casefold()))
    return replace(item, **combined)


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


def _write_custom(
    items: list[ProjectType],
    *,
    expected_revision: str | None = None,
    reference_preferences_update: dict[str, dict[str, list[str]]] | None = None,
    common_custom_references_update: dict[str, list[dict[str, str]]] | None = None,
    builtin_custom_references_update: dict[str, dict[str, list[dict[str, str]]]] | None = None,
) -> None:
    path = _store_path()
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
        existing_catalog = _read_catalog()
        saved_custom_common = _validate_common_custom_references(
            existing_catalog.get("common_custom_references", {})
            if common_custom_references_update is None
            else common_custom_references_update
        )
        saved_builtin_custom = _validate_builtin_custom_references(
            existing_catalog.get("builtin_custom_references", {})
            if builtin_custom_references_update is None
            else builtin_custom_references_update
        )
        curated_common = curated_common_references()
        effective_common = {
            field: [*curated_common[field], *saved_custom_common[field]]
            for field in REFERENCE_FIELDS
        }
        current_preferences = (
            existing_catalog.get("reference_preferences", _default_reference_preferences())
            if reference_preferences_update is None
            else reference_preferences_update
        )
        preferences = _validate_reference_preferences(
            current_preferences,
            items,
            drop_removed=(reference_preferences_update is None),
            common_override=effective_common,
            builtin_override=saved_builtin_custom,
        )
        document = {
            "schema_version": 1,
            "project_types": [item.record() for item in items],
            "reference_preferences": preferences,
            "common_custom_references": saved_custom_common,
            "builtin_custom_references": saved_builtin_custom,
        }
        payload = json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        if len(payload.encode("utf-8")) > 16_000_000:
            raise ProjectError("Custom project type catalog exceeds the storage limit")
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
    reference_preferences_update: dict[str, dict[str, list[str]]] | None = None,
    common_custom_references_update: dict[str, list[dict[str, str]]] | None = None,
    builtin_custom_references_update: dict[str, dict[str, list[dict[str, str]]]] | None = None,
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
    _write_custom(
        result,
        expected_revision=expected_revision,
        reference_preferences_update=reference_preferences_update,
        common_custom_references_update=common_custom_references_update,
        builtin_custom_references_update=builtin_custom_references_update,
    )
    return sorted(result, key=lambda item: item.name.casefold())
