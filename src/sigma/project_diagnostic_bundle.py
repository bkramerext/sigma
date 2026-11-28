"""Explicitly private, passive project diagnostic interchange (no live log hydration)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
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
_EVENT_FIELDS = {
    "type",
    "seq",
    "timestamp",
    "event_id",
    "event_kind",
    "request_id",
    "step_id",
    "attempt_id",
    "strategy_id",
    "session_id",
    "project_id",
    "cycle",
    "round",
    "turn",
    "role",
    "brainstorm_mode",
    "provider",
    "model",
    "reasoning_effort",
    "status",
    "message",
    "reason",
    "failure_type",
    "http_status",
    "provider_http_status",
    "provider_error_code",
    "provider_request_id",
    "provider_response_id",
    "provider_response_shape",
    "retry_after_seconds",
    "provider_response_channel",
    "duration_seconds",
    "usage",
    "estimated_cost_usd",
    "cost_reservation_usd",
    "token_reservation",
    "actual_cost_usd",
    "settled_cost_usd",
    "cost_status",
    "usage_status",
    "request",
    "response",
    "response_wire",
    "context_manifest",
    "context_selection_manifest",
    "dispatched_context_manifest",
    "request_snapshot",
    "response_snapshot",
    "peer_handoffs_available",
    "peer_evidence_available",
    "peer_evidence_in_actual_request",
    "peer_handoff_artifacts_in_actual_request",
    "methodology_retrieved_excerpts_in_actual_request",
    "availability",
    "handoff_id",
    "source_strategy_id",
    "source_artifact_id",
    "target_strategy_id",
    "target_artifact_id",
    "relation",
    "assessment",
    "intervention",
    "elapsed_seconds",
    "correlation_id",
    "provider_input_audit",
    "omissions",
}
_SECRET_KEY = re.compile(
    r"authorization|cookie|credential|password|secret|api[_-]?key|"
    r"access[_-]?token|refresh[_-]?token|id[_-]?token|"
    r"(^|[_-])(auth|headers|metadata|account|email|user|token)([_-]|$)",
    re.IGNORECASE,
)
_SECRET_TEXT = re.compile(
    r"(?i)(\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]+|"
    r"\b(?:authorization|cookie|token|api[_-]?key|password|access[_-]?token|refresh[_-]?token|client[_-]?secret)"
    r"['\"]?\s*[=:]\s*['\"]?[^\s,;'\"]+|"
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
        # Role inputs and provider output_text often contain serialized JSON.
        # Parse recursively rather than relying on textual token patterns.
        if value.lstrip().startswith(("{", "[")):
            try:
                parsed = json.loads(value)
            except (ValueError, RecursionError):
                pass
            else:
                if isinstance(parsed, (dict, list)):
                    cleaned = _clean(parsed, depth + 1)
                    if cleaned != parsed:
                        return _json(cleaned).decode("utf-8")
                    return value
        return _SECRET_TEXT.sub("[REDACTED]", value)
    return value


# The provider envelope is not arbitrary metadata. Keep only the documented
# non-header request body and response fields; scientific text/JSON nested
# within those fields remains private and is not a general secret detector.
_REQUEST_FIELDS = {
    "model",
    "store",
    "reasoning",
    "instructions",
    "input",
    "text",
    "stream",
    "max_output_tokens",
    "temperature",
    "top_p",
    "include",
}
_RESPONSE_FIELDS = {
    "id",
    "object",
    "created_at",
    "completed_at",
    "status",
    "model",
    "output",
    "output_text",
    "usage",
    "error",
    "incomplete_details",
    "reasoning",
}
_OUTPUT_FIELDS = {
    "id",
    "type",
    "status",
    "role",
    "content",
    "text",
    "summary",
    "refusal",
    "annotations",
    "index",
    "output_index",
    "content_index",
}


def _project_output(value: Any) -> Any:
    if isinstance(value, list):
        return [_project_output(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _project_output(item) if key in {"content", "summary"} else _clean(item)
            for key, item in value.items()
            if key in _OUTPUT_FIELDS
        }
    return _clean(value)


def _project_response(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _project_output(item) if key == "output" else _clean(item)
        for key, item in value.items()
        if key in _RESPONSE_FIELDS
    }


def sanitize_event(event: dict[str, Any]) -> dict[str, Any]:
    """Project provider envelopes; report omissions without leaking omitted keys."""
    result = {}
    omissions: set[str] = set()
    prior = event.get("omissions")
    if isinstance(prior, list):
        omissions.update(
            reason
            for reason in prior
            if reason in {
                "unknown_event_fields",
                "opaque_wire_omitted",
                "security_or_schema_projection",
            }
        )
    for key, value in event.items():
        if key == "omissions":
            continue
        if key == "response_wire":
            # Only structured response bodies can be projected safely.
            # Opaque SSE/HTTP wire text may contain transport metadata.
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                except (ValueError, RecursionError):
                    parsed = None
                if isinstance(parsed, dict):
                    cleaned = _project_response(parsed)
                    result[key] = value if cleaned == parsed else _json(cleaned).decode("utf-8")
                    if cleaned != parsed:
                        omissions.add("security_or_schema_projection")
                    continue
            omissions.add("opaque_wire_omitted")
            continue
        if key not in _EVENT_FIELDS:
            omissions.add("unknown_event_fields")
            continue
        if key in {"request", "request_snapshot", "response", "response_snapshot"}:
            if not isinstance(value, dict):
                omissions.add("security_or_schema_projection")
                continue
            cleaned = (
                {field: _clean(item) for field, item in value.items() if field in _REQUEST_FIELDS}
                if key.startswith("request")
                else _project_response(value)
            )
        elif key == "provider_input_audit":
            # Do not pass opaque compressed nested data through this projection.
            cleaned = (
                {
                    field: _clean(item)
                    for field, item in value.items()
                    if field
                    in {
                        "version",
                        "kind",
                        "status",
                        "request_body_sha256",
                        "request_body_bytes",
                    }
                }
                if isinstance(value, dict)
                else None
            )
        else:
            cleaned = _clean(value)
        if cleaned != value:
            omissions.add("security_or_schema_projection")
        result[key] = cleaned
    if omissions:
        result["omissions"] = sorted(omissions)
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
            if len(ids) > MAX_SNAPSHOTS:
                raise BundleError("Too many sessions for diagnostic export")
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
                "source_project_id",
                "source_session_id",
                "availability",
                "coverage",
                "saved_evidence",
                "events",
            }
            or not _uuid(snapshot["source_project_id"])
            or not _uuid(snapshot["source_session_id"])
            or snapshot["availability"] not in {"retained", "partial", "unavailable"}
            or snapshot["coverage"] != "best_effort_not_complete"
            or not isinstance(snapshot["saved_evidence"], dict)
            or set(snapshot["saved_evidence"]) != {
                "steps",
                "request_audits",
                "context_manifests",
                "strategy_assessments",
                "interventions",
                "cost_status",
            }
            or any(
                value is not None and (type(value) is not int or value < 0)
                for key, value in snapshot["saved_evidence"].items()
                if key != "cost_status"
            )
            or snapshot["saved_evidence"]["cost_status"]
            not in {None, "available", "unavailable", "estimated", "unknown"}
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
                or ("seq" in event and (type(event["seq"]) is not int or event["seq"] < 1))
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


def read_passive(
    source: Path, members: dict[str, bytes] | None = None, *, budget: int = MAX_DIAGNOSTIC_BYTES
) -> dict[str, bytes]:
    """Read existing passive snapshots without rereading durable directory members."""
    base = source / "diagnostics"
    if source.suffix == ".sigma" and not os.path.lexists(base):
        return {}
    if members is None:
        if source.suffix == ".sigma":
            members = project_bundle._files(source, include_private=False)
        else:
            members = project_bundle._decode(project_bundle.read_bundle(source))
    if source.suffix != ".sigma" and not any(
        project_bundle.private_diagnostic_member(name) for name in members
    ):
        return {}
    _, session_ids = _session_ids(members)
    passive: dict[str, bytes] = {}
    if source.suffix != ".sigma":
        for name, raw in members.items():
            if project_bundle.private_diagnostic_member(name):
                session_id, digest = _path_parts(name)
                if session_id not in session_ids or hashlib.sha256(raw).hexdigest() != digest:
                    raise BundleError("Invalid passive diagnostic identity")
                _add(passive, session_id, raw, budget=budget)
        return passive
    if base.is_symlink() or not base.is_dir():
        raise BundleError("Unsafe passive diagnostic directory")
    total = 0
    for root, dirs, files in os.walk(base, followlinks=False):
        relative = Path(root).relative_to(base).parts
        if len(relative) > 2 or len(dirs) > MAX_SNAPSHOTS:
            raise BundleError("Unsafe passive diagnostic directory")
        for name in dirs:
            if (
                (Path(root) / name).is_symlink()
                or (not relative and name != "private-v1")
                or (len(relative) == 1 and (not _uuid(name) or name not in session_ids))
                or len(relative) >= 2
            ):
                raise BundleError("Unsafe passive diagnostic directory")
        for filename in files:
            target = Path(root) / filename
            session_id, digest = _path_parts(target.relative_to(source).as_posix())
            info = target.lstat()
            if (
                session_id not in session_ids
                or not stat.S_ISREG(info.st_mode)
                or info.st_size > MAX_SNAPSHOT_BYTES
                or total + info.st_size > min(budget, MAX_DIAGNOSTIC_BYTES)
                or len(passive) >= MAX_SNAPSHOTS
            ):
                raise BundleError("Unsafe or oversized passive diagnostic member")
            with target.open("rb") as stream:
                raw = stream.read(info.st_size + 1)
            if len(raw) != info.st_size or hashlib.sha256(raw).hexdigest() != digest:
                raise BundleError("Passive diagnostic member changed or failed integrity check")
            _add(passive, session_id, raw, budget=budget)
            total += len(raw)
    return passive


def _saved_evidence(raw: bytes) -> dict[str, Any]:
    """Index existing durable fields without copying or manufacturing provider history."""
    record = json.loads(raw)
    steps = record.get("steps")

    def count(key: str) -> int | None:
        value = record.get(key)
        return len(value) if isinstance(value, list) else None

    def step_count(key: str) -> int | None:
        if not isinstance(steps, list):
            return None
        return sum(isinstance(step, dict) and isinstance(step.get(key), dict) for step in steps)

    cost = record.get("cost_status")
    return {
        "steps": count("steps"),
        "request_audits": step_count("provider_input_audit"),
        "context_manifests": step_count("context_manifest"),
        "strategy_assessments": count("strategy_assessments"),
        "interventions": count("interventions"),
        "cost_status": (
            cost
            if isinstance(cost, str)
            and cost in {"available", "unavailable", "estimated", "unknown"}
            else None
        ),
    }


def capture(source: Path, members: dict[str, bytes], *, budget: int) -> dict[str, bytes]:
    """Read only authorized project-owned logs, without creating or replaying them."""
    from sigma import session_log

    project_id, session_ids = _session_ids(members)
    passive = read_passive(source, members, budget=budget)
    for session_id in sorted(session_ids):
        target = session_log.log_path(str(source), project_id, session_id)
        events: list[dict[str, Any]] = []
        availability = "unavailable"
        # Logs are best effort; do not block research or flush unrelated queues.
        # A read can observe a torn record, so retained is never "complete".
        with session_log._lock(target):
            if target.is_symlink():
                raise BundleError("Unsafe diagnostic log path")
            if target.is_file():
                info = target.lstat()
                if (
                    info.st_size > session_log.MAX_LOG_BYTES + 4096
                    or info.st_uid != os.geteuid()
                    or info.st_mode & 0o077
                ):
                    raise BundleError("Unsafe diagnostic log ownership, permissions or size")
                frames, _ = session_log._frames(target)
                with target.open("rb") as stream:
                    marker_count = sum(line.startswith(b"<!-- SIGMA_EVENT ") for line in stream)
                if marker_count != len(frames):
                    availability = "partial"
                if len(frames) > MAX_EVENTS:
                    raise BundleError("Too many diagnostic events")
                remaining = min(budget, MAX_DIAGNOSTIC_BYTES) - sum(map(len, passive.values()))
                event_bytes = 0
                for frame in frames:
                    event = sanitize_event(frame)
                    event_bytes += len(_json(event)) + 1
                    if event_bytes > min(remaining, MAX_SNAPSHOT_BYTES):
                        raise BundleError("Diagnostic event budget exceeded")
                    events.append(event)
                if events:
                    sequences = [event.get("seq") for event in events]
                    gap = any(
                        type(seq) is not int or seq != index
                        for index, seq in enumerate(sequences, 1)
                    )
                    availability = (
                        "partial"
                        if availability == "partial"
                        or gap
                        or any(
                            event.get("type") in {"retention_limit", "event_omitted"}
                            for event in events
                        )
                        else "retained"
                    )
        # Imported originals already explain missing live history; don't add a
        # new empty snapshot on every copy/re-export.
        if availability == "unavailable" and any(
            _path_parts(name)[0] == session_id for name in passive
        ):
            continue
        raw = _json(
            {
                "source_project_id": project_id,
                "source_session_id": session_id,
                "availability": availability,
                "coverage": "best_effort_not_complete",
                "saved_evidence": _saved_evidence(members[f"research-sessions/{session_id}.json"]),
                "events": events,
            }
        )
        _add(passive, session_id, raw, budget=budget)
    return passive


def encode(passive: dict[str, bytes]) -> dict[str, Any]:
    """Deduplicate immutable snapshots by digest, independently of their mapping."""
    mappings: dict[str, list[str]] = {}
    blobs: dict[str, Any] = {}
    for name, raw in sorted(passive.items()):
        session_id, digest = _path_parts(name)
        mappings.setdefault(session_id, []).append(digest)
        if digest not in blobs:
            _validate_snapshot(raw, digest)
            blobs[digest] = project_bundle._compressed_member(raw)
        elif hashlib.sha256(raw).hexdigest() != digest:
            raise BundleError("Conflicting diagnostic snapshot bytes")
    return {"version": _VERSION, "private": True, "sessions": mappings, "blobs": blobs}


def decode(
    payload: Any, members: dict[str, bytes], *, budget: int
) -> dict[str, bytes]:
    project_id, session_ids = _session_ids(members)
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
    decoded = project_bundle._decode(
        {
            "format": project_bundle.FORMAT,
            "version": project_bundle.VERSION,
            "files": {
                "project.json": {"schema_version": 13},
                **{f"{digest}.bin": entry for digest, entry in blobs.items()},
            },
        }
    )
    passive = {}
    validated = {}
    source_mappings = {}
    for session_id, digest in references:
        raw = decoded[f"{digest}.bin"]
        if digest not in validated:
            _validate_snapshot(raw, digest)
            snapshot = json.loads(raw)
            validated[digest] = (snapshot["source_project_id"], snapshot["source_session_id"])
        source_project, source_session = validated[digest]
        # Original source IDs are untrusted declarations, not authenticated
        # provenance. Within the current project they must agree with mapping.
        if (
            source_project == project_id
            and source_session in session_ids
            and source_session != session_id
        ):
            raise BundleError("Diagnostic source/session mapping mismatch")
        previous = source_mappings.setdefault((source_project, source_session), session_id)
        if previous != session_id:
            raise BundleError("Diagnostic source mapped to multiple current sessions")
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
