"""Explicitly private, passive project diagnostic interchange (no live log hydration)."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from uuid import UUID

from sigma import project_bundle
from sigma.project_bundle import BundleError

PREFIX = "diagnostics/private-v1/"
MAX_DIAGNOSTIC_BYTES = 128 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 48 * 1024 * 1024
MAX_SNAPSHOTS = 2048
MAX_EVENTS = 100000
_VERSION = 1

# Only recorded research diagnostics, not transport headers or account metadata.
_EVENT_FIELDS = frozenset("""
    type seq timestamp event_id event_kind request_id step_id attempt_id strategy_id
    session_id project_id cycle round turn role brainstorm_mode provider model reasoning_effort
    status message reason failure_type http_status provider_http_status provider_error_code
    provider_request_id provider_response_id provider_response_shape retry_after_seconds
    provider_response_channel duration_seconds usage estimated_cost_usd cost_reservation_usd
    token_reservation actual_cost_usd settled_cost_usd cost_status usage_status
    request response response_wire context_manifest context_selection_manifest
    dispatched_context_manifest request_snapshot response_snapshot
    peer_handoffs_available peer_evidence_available peer_evidence_in_actual_request
    peer_handoff_artifacts_in_actual_request methodology_retrieved_excerpts_in_actual_request
    availability handoff_id source_strategy_id source_artifact_id target_strategy_id
    target_artifact_id relation assessment intervention
""".split())
_SECRET_KEY = re.compile(
    r"authorization|cookie|credential|password|secret|api[_-]?key|"
    r"access[_-]?token|refresh[_-]?token|id[_-]?token|"
    r"(^|[_-])(headers|metadata|account|email|user|token)([_-]|$)",
    re.I,
)
_SECRET_TEXT = re.compile(
    r"(?i)(\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]+|"
    r"\b(?:api[_-]?key|password|access[_-]?token|refresh[_-]?token|client[_-]?secret)"
    r"\s*[=:]\s*['\"]?[^\s,;'\"]+|"
    r"\bsk-[A-Za-z0-9_-]{16,}\b|"
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b)"
)


def _json(value: Any) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise BundleError("Invalid diagnostic JSON") from exc


def _uuid(value: Any) -> bool:
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, TypeError):
        return False


def _clean(value: Any, depth: int = 0) -> Any:
    if depth > 64:
        raise BundleError("Diagnostic nesting exceeds the allowed depth")
    if isinstance(value, dict):
        return {
            key: _clean(item, depth + 1)
            for key, item in value.items()
            if isinstance(key, str) and not _SECRET_KEY.search(key)
        }
    if isinstance(value, list):
        return [_clean(item, depth + 1) for item in value]
    if isinstance(value, str):
        return _SECRET_TEXT.sub("[REDACTED]", value)
    return value


def sanitize_event(event: dict[str, Any]) -> dict[str, Any]:
    """Keep the allowlisted envelope; remove secret-bearing nested metadata."""
    result = {
        key: _clean(value)
        for key, value in event.items()
        if key in _EVENT_FIELDS and key != "response_wire"
    }
    # Wire text may contain opaque headers, SSE metadata or credentials. Preserve
    # only safe structured JSON; never export an opaque wire string.
    wire = event.get("response_wire")
    if isinstance(wire, str):
        try:
            parsed = json.loads(wire)
            if isinstance(parsed, (dict, list)):
                cleaned = _clean(parsed)
                result["response_wire"] = (
                    wire if cleaned == parsed else _json(cleaned).decode("utf-8")
                )
        except (ValueError, RecursionError):
            pass
    return result


def _session_ids(members: dict[str, bytes]) -> tuple[str, set[str]]:
    try:
        project_id = json.loads(members["project.json"])["id"]
        if not _uuid(project_id):
            raise ValueError("project identifier")
        ids = set()
        for name, raw in members.items():
            match = re.fullmatch(r"research-sessions/([0-9a-f-]{36})\.json", name)
            if match is None:
                continue
            session_id = match[1]
            record = json.loads(raw)
            if (
                not _uuid(session_id)
                or record.get("id") != session_id
                or record.get("project_id") != project_id
            ):
                raise ValueError("session identity")
            ids.add(session_id)
        return project_id, ids
    except (KeyError, TypeError, ValueError, AttributeError, UnicodeError) as exc:
        raise BundleError("Invalid diagnostic project/session identity") from exc


def _validate_snapshot(raw: bytes, digest: str) -> None:
    if len(raw) > MAX_SNAPSHOT_BYTES or hashlib.sha256(raw).hexdigest() != digest:
        raise BundleError("Diagnostic snapshot size or digest mismatch")
    try:
        snapshot = json.loads(raw)
        if (
            not isinstance(snapshot, dict)
            or set(snapshot) != {
                "source_project_id", "source_session_id", "availability", "events"
            }
            or not _uuid(snapshot["source_project_id"])
            or not _uuid(snapshot["source_session_id"])
            or snapshot["availability"] not in {"available", "partial", "unavailable"}
            or not isinstance(snapshot["events"], list)
            or len(snapshot["events"]) > MAX_EVENTS
            or (snapshot["availability"] == "unavailable" and snapshot["events"])
        ):
            raise BundleError("Invalid diagnostic snapshot schema")
        for event in snapshot["events"]:
            if (
                not isinstance(event, dict)
                or not isinstance(event.get("type"), str)
                or not event["type"]
                or sanitize_event(event) != event
                or event.get("project_id", snapshot["source_project_id"])
                != snapshot["source_project_id"]
                or event.get("session_id", snapshot["source_session_id"])
                != snapshot["source_session_id"]
            ):
                raise BundleError("Unsafe diagnostic event")
        if _json(snapshot) != raw:
            raise BundleError("Diagnostic snapshot is not canonical JSON")
    except (ValueError, TypeError, KeyError, RecursionError, UnicodeError) as exc:
        raise BundleError("Invalid diagnostic snapshot") from exc


def _path_parts(name: str) -> tuple[str, str]:
    match = re.fullmatch(
        re.escape(PREFIX) + r"([0-9a-f-]{36})/([0-9a-f]{64})\.bin", name
    )
    if match is None or not _uuid(match[1]):
        raise BundleError("Unsafe passive diagnostic path")
    return match[1], match[2]


def _add(
    passive: dict[str, bytes], session_id: str, raw: bytes, *, budget: int
) -> None:
    digest = hashlib.sha256(raw).hexdigest()
    name = f"{PREFIX}{session_id}/{digest}.bin"
    if name in passive:
        return
    if (
        len(passive) >= MAX_SNAPSHOTS
        or len(raw) > MAX_SNAPSHOT_BYTES
        or sum(map(len, passive.values())) + len(raw) > min(budget, MAX_DIAGNOSTIC_BYTES)
    ):
        raise BundleError("Diagnostic snapshot budget exceeded")
    _validate_snapshot(raw, digest)
    passive[name] = raw


def capture(
    source: Path, members: dict[str, bytes], *, budget: int
) -> dict[str, bytes]:
    """Read only authorized project-owned logs, without creating or replaying them."""
    from sigma import session_log

    project_id, session_ids = _session_ids(members)
    passive: dict[str, bytes] = {}
    for name, raw in members.items():
        if name.startswith(PREFIX):
            session_id, digest = _path_parts(name)
            if session_id not in session_ids:
                raise BundleError("Passive diagnostics reference an unknown session")
            _validate_snapshot(raw, digest)
            _add(passive, session_id, raw, budget=budget)
    for session_id in sorted(session_ids):
        target = session_log.log_path(str(source), project_id, session_id)
        events: list[dict[str, Any]] = []
        availability = "unavailable"
        with session_log._lock(target):
            if target.is_symlink():
                raise BundleError("Unsafe diagnostic log path")
            if target.is_file():
                if target.stat().st_size > session_log.MAX_LOG_BYTES + 4096:
                    raise BundleError("Diagnostic log exceeds its retention bound")
                frames, _ = session_log._frames(target)
                if len(frames) > MAX_EVENTS:
                    raise BundleError("Too many diagnostic events")
                events = [sanitize_event(event) for event in frames]
                if events:
                    availability = (
                        "partial"
                        if any(
                            event.get("type") in {"retention_limit", "event_omitted"}
                            for event in events
                        )
                        else "available"
                    )
        # Imported originals already explain missing live history; don't add a
        # new empty snapshot on every copy/re-export.
        if not events and any(_path_parts(name)[0] == session_id for name in passive):
            continue
        raw = _json({
            "source_project_id": project_id,
            "source_session_id": session_id,
            "availability": availability,
            "events": events,
        })
        _add(passive, session_id, raw, budget=budget)
    return passive


def encode(passive: dict[str, bytes]) -> dict[str, Any]:
    """Deduplicate immutable snapshots by digest, independently of their mapping."""
    mappings: dict[str, list[str]] = {}
    blobs: dict[str, Any] = {}
    for name, raw in sorted(passive.items()):
        session_id, digest = _path_parts(name)
        _validate_snapshot(raw, digest)
        mappings.setdefault(session_id, []).append(digest)
        if digest not in blobs:
            blobs[digest] = project_bundle._compressed_member(raw)
    return {"version": _VERSION, "private": True, "sessions": mappings, "blobs": blobs}


def decode(
    payload: Any, members: dict[str, bytes], *, budget: int
) -> dict[str, bytes]:
    _, session_ids = _session_ids(members)
    if (
        not isinstance(payload, dict)
        or set(payload) != {"version", "private", "sessions", "blobs"}
        or type(payload["version"]) is not int
        or payload["version"] != _VERSION
        or payload["private"] is not True
        or not isinstance(payload["sessions"], dict)
        or not isinstance(payload["blobs"], dict)
        or len(payload["blobs"]) > MAX_SNAPSHOTS
        or len(payload["sessions"]) > MAX_SNAPSHOTS
    ):
        raise BundleError("Invalid private diagnostic archive")
    blobs = payload["blobs"]
    mappings = payload["sessions"]
    references: list[tuple[str, str]] = []
    total = 0
    for session_id, digests in mappings.items():
        if (
            session_id not in session_ids
            or not isinstance(digests, list)
            or len(digests) > MAX_SNAPSHOTS
        ):
            raise BundleError("Invalid diagnostic session mapping")
        seen = set()
        for digest in digests:
            if (
                not isinstance(digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                or digest in seen
                or digest not in blobs
                or len(references) >= MAX_SNAPSHOTS
            ):
                raise BundleError("Invalid or duplicate diagnostic reference")
            seen.add(digest)
            entry = blobs[digest]
            if (
                not isinstance(entry, dict)
                or set(entry) != {"$sigma_bundle_encoding", "size", "data"}
                or entry["$sigma_bundle_encoding"] != "zstd+base64"
                or type(entry["size"]) is not int
                or not 0 < entry["size"] <= MAX_SNAPSHOT_BYTES
                or not isinstance(entry["data"], str)
            ):
                raise BundleError("Invalid diagnostic member metadata")
            total += entry["size"]
            if total > min(budget, MAX_DIAGNOSTIC_BYTES):
                raise BundleError("Diagnostic decompression budget exceeded")
            references.append((session_id, digest))
    if {digest for _, digest in references} != set(blobs):
        raise BundleError("Unreferenced diagnostic member")
    if sum(len(entry["data"]) for entry in blobs.values()) > MAX_DIAGNOSTIC_BYTES * 2:
        raise BundleError("Diagnostic compressed size budget exceeded")
    # Existing bounded zstd decoder checks declared length and trailing bytes.
    decoded = project_bundle._decode({
        "format": project_bundle.FORMAT,
        "version": project_bundle.VERSION,
        "files": {
            "project.json": {"schema_version": 13},
            **{f"{digest}.bin": entry for digest, entry in blobs.items()},
        },
    })
    passive = {}
    for session_id, digest in references:
        raw = decoded[f"{digest}.bin"]
        _validate_snapshot(raw, digest)
        passive[f"{PREFIX}{session_id}/{digest}.bin"] = raw
    return passive


def rebind(passive: dict[str, bytes], session_ids: dict[str, str]) -> dict[str, bytes]:
    """Rekey only the mapping path; never rewrite immutable source evidence."""
    result = {}
    for name, raw in passive.items():
        session_id, digest = _path_parts(name)
        if session_id not in session_ids:
            raise BundleError("Missing imported diagnostic session mapping")
        result[f"{PREFIX}{session_ids[session_id]}/{digest}.bin"] = raw
    return result
