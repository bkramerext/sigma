"""Rebase project-owned identities while cloning a complete SIGMA project.

The source bundle is immutable. Rebinding happens in memory before the importer
atomically publishes a new project; preserve binary artifacts byte-for-byte.
"""

from __future__ import annotations

import hashlib
import json
import re
import zlib
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sigma.project_bundle import _decode, portable_bundle
from sigma.projects import ProjectError

_SESSION_FILE = re.compile(r"research-sessions/([0-9a-f-]{36})\.json$")
_FROZEN_FILE = re.compile(r"artifacts/papers/snapshots/([0-9a-f]{64})\.json\.zlib$")
_SKIPPED_SESSION_FILES = {
    "research-sessions/limits.json",
    "research-sessions/sequence.json",
    "research-sessions/obligation-ids.json",
}
_MAX_FROZEN_BYTES = 128 * 1024 * 1024


def _canonical(value: Any) -> bytes:
    """Match the canonical digest used by sigma.papers._json."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _encode(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _member_name(name: str) -> str:
    """Legacy .sigma paper records must become visible to .json readers."""
    if name.startswith("papers/.snapshots/"):
        return "artifacts/papers/snapshots/" + name[len("papers/.snapshots/") :]
    if name.startswith("papers/"):
        return "artifacts/papers/" + name[len("papers/") :]
    if name.startswith("agentic-runs/"):
        return "evidence/agentic-runs/" + name[len("agentic-runs/") :]
    return name


def _rewrite(value: Any, substitutions: dict[str, str]) -> Any:
    if isinstance(value, str):
        for old, new in substitutions.items():
            if old in value:
                value = value.replace(old, new)
        return value
    if isinstance(value, list):
        return [_rewrite(item, substitutions) for item in value]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            updated_key = _rewrite(key, substitutions)
            if updated_key in result:
                raise ProjectError("Copied project contains colliding evidence references.")
            result[updated_key] = _rewrite(item, substitutions)
        return result
    return value


def rebase_copy(
    bundle: dict[str, Any],
    *,
    source_id: str,
    new_id: str,
    source_path: str,
    destination_path: str,
    session_ids_out: dict[str, str] | None = None,
    session_numbers_out: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Return a portable, independently identified project bundle.

    Session IDs are project-owned work identifiers in the shared hosted ledger,
    so each copied session also receives a new UUID. Strategy, paper, run,
    artifact and execution IDs stay stable within the copy; their owners and
    links are updated, preserving local evidence relationships.

    Frozen paper evidence is content-addressed. Rebase its source references,
    recompute the digest and rename compressed archives as one operation.
    """
    from sigma.project_bundle import BundleError

    try:
        members = _decode(bundle)
        original = json.loads(members["project.json"])
        if original.get("id") != new_id:
            raise ProjectError("Save As requires the new project identity.")
        source = Path(source_path).resolve()
        destination = Path(destination_path).resolve()
        if source == destination or source_id == new_id:
            raise ProjectError("Save As must create a different project.")
        session_ids: dict[str, str] = {}
        admission_keys: dict[str, str] = {}
        session_numbers: dict[str, int] = {}
        historical_paths: set[str] = set()
        for name, data in members.items():
            if name in _SKIPPED_SESSION_FILES:
                continue
            match = _SESSION_FILE.fullmatch(name)
            if match is None:
                continue
            old_session_id = match.group(1)
            if str(UUID(old_session_id)) != old_session_id:
                raise ProjectError("Cannot copy a noncanonical research session.")
            session = json.loads(data)
            if (
                not isinstance(session, dict)
                or session.get("id") != old_session_id
                or session.get("project_id") != source_id
            ):
                raise ProjectError("Cannot copy a foreign or invalid research session.")
            if session.get("status") in {"queued", "running"}:
                raise ProjectError("Stop active research before saving a copy of this project.")
            session_ids[old_session_id] = str(uuid4())
            session_numbers[old_session_id] = int(session.get("session_number", 1))
            original_key = session.get("idempotency_key")
            if original_key is not None:
                if (
                    not isinstance(original_key, str)
                    or not original_key
                    or original_key in admission_keys
                ):
                    raise ProjectError("Cannot copy an ambiguous session admission key.")
                admission_keys[original_key] = str(uuid4())
            prior_path = session.get("project_path")
            if isinstance(prior_path, str) and prior_path.startswith("/"):
                historical_paths.add(prior_path)

        # Longer strings first so a canonical path/UUID inside a reference is
        # not partially transformed by a shorter overlapping substitution.
        substitutions = {
            str(source): str(destination),
            **{path: str(destination) for path in historical_paths},
            source_id: new_id,
            **session_ids,
            **admission_keys,
        }
        substitutions = dict(
            sorted(substitutions.items(), key=lambda pair: len(pair[0]), reverse=True)
        )
        rekeyed: dict[str, bytes] = {}
        for old_name, raw in members.items():
            name = _rewrite(_member_name(old_name), substitutions)
            if name in rekeyed:
                raise ProjectError("Copied project contains duplicate storage members.")
            rekeyed[name] = raw

        # Rewrite content-addressed frozen snapshots first. Any record that
        # points to one must follow its renamed digest.
        digest_map: dict[str, str] = {}
        rewritten: dict[str, bytes] = {}
        for name, raw in rekeyed.items():
            match = _FROZEN_FILE.fullmatch(name)
            if match is None:
                rewritten[name] = raw
                continue
            old_digest = match.group(1)
            expanded = zlib.decompressobj()
            decoded = expanded.decompress(raw, _MAX_FROZEN_BYTES + 1)
            if len(decoded) > _MAX_FROZEN_BYTES or not expanded.eof or expanded.unused_data:
                raise ProjectError("Frozen paper evidence is too large or incomplete.")
            decoded += expanded.flush()
            if hashlib.sha256(decoded).hexdigest() != old_digest:
                raise ProjectError("Frozen paper evidence failed integrity validation.")
            original_package = json.loads(decoded)
            if (
                not isinstance(original_package, dict)
                or original_package.get("project_id") != source_id
                or original_package.get("schema") != "sigma-paper-evidence-v2"
            ):
                raise ProjectError("Frozen paper evidence belongs to a different project.")
            package = _rewrite(original_package, substitutions)
            encoded = _canonical(package)
            new_digest = hashlib.sha256(encoded).hexdigest()
            digest_map[old_digest] = new_digest
            target_name = f"artifacts/papers/snapshots/{new_digest}.json.zlib"
            if target_name in rewritten:
                raise ProjectError("Copied frozen evidence hash collision.")
            rewritten[target_name] = zlib.compress(encoded, level=6)

        # Rebase every JSON record, not just the session's top-level fields:
        # paper metadata, Q/A, citations, run/execution ownership and nested
        # research artifacts all carry project/session references.
        staged: dict[str, Any] = {}
        for name, raw in rewritten.items():
            if not name.endswith(".json"):
                staged[name] = raw
                continue
            try:
                data = json.loads(raw)
            except (UnicodeDecodeError, ValueError):
                # Historical non-JSON attachments are retained losslessly.
                # Reject those containing the source identity rather than
                # silently claiming a complete identity cascade.
                if source_id.encode() in raw:
                    raise ProjectError(
                        f"Cannot rebind references in unreadable JSON member {name}."
                    ) from None
                staged[name] = raw
                continue
            original_data = data
            data = _rewrite(data, substitutions)
            session_match = _SESSION_FILE.fullmatch(name)
            if session_match is not None and isinstance(data, dict):
                if not isinstance(data.get("idempotency_key"), str):
                    data["idempotency_key"] = str(uuid4())
            if name == "artifacts/research-qa/records.json" and isinstance(data, dict):
                # An in-flight question belongs to the original provider request.
                # A clone must never replay it using the old request identity.
                data["pending_requests"] = []
                old_records = original_data.get("records", []) if isinstance(original_data, dict) else []
                new_records = data.get("records", [])
                if isinstance(old_records, list) and isinstance(new_records, list):
                    for old_record, copied_record in zip(old_records, new_records):
                        if not isinstance(old_record, dict) or not isinstance(copied_record, dict):
                            continue
                        original_digest = old_record.get("snapshot_sha256")
                        if not isinstance(original_digest, str):
                            continue
                        copied_record["source_snapshot_sha256"] = old_record.get(
                            "source_snapshot_sha256", original_digest
                        )
                        copied_record["snapshot_derivation"] = "save_as_rebased_selected_sources_v1"
                        derivative = {
                            "schema": "sigma.qa.rebased-selected-sources-v1",
                            "project_id": new_id,
                            "evidence_snapshot": copied_record.get("evidence_snapshot", []),
                        }
                        copied_record["snapshot_sha256"] = hashlib.sha256(
                            _canonical(derivative)
                        ).hexdigest()
                        before_answer = old_record.get("answer")
                        if isinstance(before_answer, str) and before_answer != copied_record.get("answer"):
                            copied_record["source_answer_sha256"] = hashlib.sha256(
                                before_answer.encode("utf-8")
                            ).hexdigest()
            if isinstance(data, dict):
                inline = data.get("snapshot")
                if isinstance(inline, dict) and inline.get("schema") == "sigma-paper-evidence-v2":
                    digest = hashlib.sha256(_canonical(inline)).hexdigest()
                    old = data.get("snapshot_sha256")
                    if isinstance(old, str):
                        digest_map[old] = digest
                    data["snapshot_sha256"] = digest
                frozen = data.get("frozen_package")
                if isinstance(frozen, dict) and frozen.get("schema") == "sigma-paper-evidence-v2":
                    digest = hashlib.sha256(_canonical(frozen)).hexdigest()
                    old = data.get("snapshot_sha256")
                    if isinstance(old, str):
                        digest_map[old] = digest
                    data["snapshot_sha256"] = digest
            staged[name] = data

        # References to separately archived snapshots and their digest fields
        # must agree with the rebased immutable bytes. Q/A historical digests
        # without an archived source remain unchanged, as provenance.
        for name, record in list(staged.items()):
            if isinstance(record, (dict, list)):
                record = _rewrite(record, digest_map)
                if isinstance(record, dict):
                    for key in ("snapshot_ref", "frozen_package_ref"):
                        if key in record and record[key] not in digest_map.values():
                            raise ProjectError(
                                f"Copied paper references unavailable frozen evidence: {name}."
                            )
                staged[name] = _encode(record)
        if session_ids_out is not None:
            session_ids_out.update(session_ids)
        if session_numbers_out is not None:
            session_numbers_out.update(session_numbers)
        return portable_bundle(staged)
    except (BundleError, OSError, UnicodeDecodeError, ValueError, TypeError, zlib.error) as exc:
        if isinstance(exc, ProjectError):
            raise
        raise ProjectError(f"Cannot safely rebind copied project: {exc}") from exc
