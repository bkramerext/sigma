"""Version-4 project interchange. Runtime storage stays on disk.

The interchange has human-readable/nonartifact project members and exactly one
zstd-compressed TAR archive containing all artifacts/. Older bundle versions
can be imported safely and are migrated to the new disk-backed format.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path
from uuid import uuid4

from sigma import project_bundle
from sigma.project_bundle import BundleError
from sigma.zstd_codec import (
    MAX_BUNDLE_BYTES,
    MAX_COMPRESSED_MEMBER_BYTES,
    MAX_MEMBER_BYTES,
    ZstdCodecError,
    compress_archive,
    decompress_archive,
)

FORMAT = project_bundle.FORMAT
VERSION = 4
ARCHIVE_ENCODING = "tar+zstd+base64"
MAX_ARTIFACT_FILES = 10000
# Files remain individually bounded, but a TAR may hold multiple files.
# Encode it as consecutive bounded zstd frames rather than limiting the
# entire project to one 256 MiB frame.
MAX_ARCHIVE_BYTES = MAX_BUNDLE_BYTES
MAX_ARCHIVE_FRAME_BYTES = MAX_MEMBER_BYTES


def _canon(name: str) -> str:
    """Canonicalize legacy artifact paths only while exporting live projects."""
    if name.startswith("papers/.snapshots/"):
        return "artifacts/generated_papers/.snapshots/" + name[len("papers/.snapshots/") :]
    if name.startswith("papers/"):
        return "artifacts/generated_papers/" + name[len("papers/") :]
    if name.startswith("artifacts/papers/snapshots/"):
        return "artifacts/generated_papers/.snapshots/" + name[len("artifacts/papers/snapshots/") :]
    if name.startswith("artifacts/papers/"):
        return "artifacts/generated_papers/" + name[len("artifacts/papers/") :]
    return name


def _safe_name(name: str) -> bool:
    return (
        isinstance(name, str)
        and bool(name)
        and "\\" not in name
        and not name.startswith("/")
        and all(part not in {"", ".", ".."} for part in name.split("/"))
    )


def _archive(artifacts: dict[str, bytes]) -> dict:
    output = io.BytesIO()
    size = 0
    if len(artifacts) > MAX_ARTIFACT_FILES:
        raise BundleError("Too many project artifacts for export")
    with tarfile.open(fileobj=output, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for name, data in sorted(artifacts.items()):
            if not name.startswith("artifacts/") or not _safe_name(name):
                raise BundleError("Invalid source artifact path")
            size += len(data)
            if len(data) > MAX_MEMBER_BYTES or size > MAX_BUNDLE_BYTES:
                raise BundleError("Source artifacts exceed the project bundle size limit")
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            info.mode = 0o600
            tar.addfile(info, io.BytesIO(data))
    uncompressed = output.getvalue()
    if len(uncompressed) > MAX_ARCHIVE_BYTES:
        raise BundleError("Source artifacts exceed the compressed archive input limit")
    try:
        packed = compress_archive(uncompressed, MAX_ARCHIVE_FRAME_BYTES)
    except ZstdCodecError as exc:
        raise BundleError(f"Source artifact archive compression failed: {exc}") from exc
    return {
        "encoding": ARCHIVE_ENCODING,
        "uncompressed_size": len(uncompressed),
        "sha256": hashlib.sha256(uncompressed).hexdigest(),
        "data": base64.b64encode(packed).decode("ascii"),
    }


def _unarchive(entry: object) -> dict[str, bytes]:
    if (
        not isinstance(entry, dict)
        or set(entry) != {"encoding", "uncompressed_size", "sha256", "data"}
        or entry["encoding"] != ARCHIVE_ENCODING
    ):
        raise BundleError("Invalid Source Material/paper archive")
    expected = entry["uncompressed_size"]
    digest = entry["sha256"]
    encoded = entry["data"]
    if (
        type(expected) is not int
        or expected < 0
        or expected > MAX_ARCHIVE_BYTES
        or not isinstance(digest, str)
        or re.fullmatch("[0-9a-f]{64}", digest) is None
        or not isinstance(encoded, str)
    ):
        raise BundleError("Invalid source artifact archive metadata")
    frames = max(1, (expected + MAX_ARCHIVE_FRAME_BYTES - 1) // MAX_ARCHIVE_FRAME_BYTES)
    max_encoded = ((frames * MAX_COMPRESSED_MEMBER_BYTES + 2) // 3) * 4 + 4
    if len(encoded) > max_encoded:
        raise BundleError("Source artifact archive exceeds the compressed size limit")
    try:
        compressed = base64.b64decode(encoded, validate=True)
        raw = decompress_archive(compressed, expected, MAX_ARCHIVE_FRAME_BYTES)
    except (binascii.Error, ValueError, ZstdCodecError) as exc:
        raise BundleError("Cannot decode the Source Material/paper archive") from exc
    if hashlib.sha256(raw).hexdigest() != digest:
        raise BundleError("Source artifact archive checksum mismatch")
    artifacts: dict[str, bytes] = {}
    size = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tar:
            for member in tar:
                name = member.name
                if (
                    not member.isfile()
                    or not name.startswith("artifacts/")
                    or not _safe_name(name)
                    or name in artifacts
                    or len(artifacts) >= MAX_ARTIFACT_FILES
                    or member.size > MAX_MEMBER_BYTES
                ):
                    raise BundleError("Unsafe Source Material/paper archive member")
                handle = tar.extractfile(member)
                if handle is None:
                    raise BundleError("Missing source artifact bytes")
                payload = handle.read(member.size + 1)
                if len(payload) != member.size:
                    raise BundleError("Truncated source artifact")
                size += len(payload)
                if size > MAX_BUNDLE_BYTES:
                    raise BundleError("Source artifacts exceed the project size limit")
                artifacts[name] = payload
    except (tarfile.TarError, OSError, EOFError) as exc:
        raise BundleError("Invalid Source Material/paper archive") from exc
    return artifacts


def make_bundle(members: dict[str, bytes]) -> dict:
    standard: dict[str, bytes] = {}
    artifacts: dict[str, bytes] = {}
    for original, data in members.items():
        name = _canon(original)
        if not _safe_name(name):
            raise BundleError("Unsafe project member name")
        target = artifacts if name.startswith("artifacts/") else standard
        if name in target:
            raise BundleError(f"Conflicting project members: {name}")
        target[name] = data
    if "project.json" not in standard:
        raise BundleError("Cannot export a project without project.json")
    if sum(map(len, standard.values())) + sum(map(len, artifacts.values())) > MAX_BUNDLE_BYTES:
        raise BundleError("Project members exceed the total bundle size limit")
    encoded_standard = project_bundle.portable_bundle(standard)["files"]
    return {
        "format": FORMAT,
        "version": VERSION,
        "files": encoded_standard,
        "artifacts": _archive(artifacts),
    }


def export_project(path: str | Path) -> bytes:
    source = Path(path)
    if source.suffix == ".sigma" and source.is_dir():
        members = project_bundle._files(source)
    elif source.suffix == ".json" and source.is_file():
        # Transitional live projects are decoded for export; this does not
        # authorize importing any old external bundle version.
        members = project_bundle._decode(project_bundle.read_bundle(source))
    else:
        raise BundleError("Invalid project source")
    return (
        json.dumps(make_bundle(members), sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")


def decode_bundle(payload: dict) -> dict[str, bytes]:
    # Historical exports must remain importable after the runtime moves to
    # directory-backed projects. The legacy decoder validates member names,
    # size bounds and content encoding before any files are published.
    if (
        isinstance(payload, dict)
        and set(payload) == {"format", "version", "files"}
        and payload.get("format") == FORMAT
        and payload.get("version")
        in {
            project_bundle.LEGACY_VERSION,
            project_bundle.LEGACY_PORTABLE_VERSION,
            project_bundle.VERSION,
        }
    ):
        legacy = project_bundle._decode(payload)
        migrated: dict[str, bytes] = {}
        for original, data in legacy.items():
            name = _canon(original)
            if not _safe_name(name) or name in migrated:
                raise BundleError("Conflicting legacy project artifact path")
            migrated[name] = data
        return migrated
    if (
        not isinstance(payload, dict)
        or set(payload) != {"format", "version", "files", "artifacts"}
        or payload["format"] != FORMAT
        or payload["version"] != VERSION
        or not isinstance(payload["files"], dict)
        or any(name.startswith("artifacts/") for name in payload["files"])
    ):
        raise BundleError("Unsupported or malformed project bundle")
    standard = project_bundle._decode(
        {
            "format": FORMAT,
            "version": project_bundle.VERSION,
            "files": payload["files"],
        }
    )
    artifacts = _unarchive(payload["artifacts"])
    if set(standard).intersection(artifacts):
        raise BundleError("Duplicate project member")
    if sum(map(len, standard.values())) + sum(map(len, artifacts.values())) > MAX_BUNDLE_BYTES:
        raise BundleError("Project members exceed the total bundle size limit")
    return {**standard, **artifacts}


def bundle_document(payload: dict) -> dict:
    members = decode_bundle(payload)
    try:
        from sigma.projects import _decode as decode_project

        document = json.loads(members["project.json"])
        decode_project(document)
        return document
    except (KeyError, ValueError, TypeError, UnicodeDecodeError) as exc:
        raise BundleError("Imported project document is invalid") from exc


def import_project(
    payload: dict,
    destination: str | Path,
    *,
    independent: bool = True,
    preserve_identity: bool = False,
    title_override: str | None = None,
) -> Path:
    """Validate, reidentify, and restore an imported bundle as a real directory."""
    from sigma.project_copy import rebase_copy
    from sigma.projects import _decode as validate_project

    destination = Path(destination)
    if destination.suffix != ".sigma" or destination.exists():
        raise BundleError("Import destination must be a new .sigma directory")
    members = decode_bundle(payload)
    if title_override is not None:
        renamed = project_bundle.rename_bundle_project(
            project_bundle.portable_bundle(members), title_override
        )
        members = project_bundle._decode(renamed)
    document = json.loads(members["project.json"])
    validate_project(document)
    if independent or preserve_identity:
        old_id = document["id"]
        new_id = str(uuid4()) if independent else old_id
        document["id"] = new_id
        members["project.json"] = (
            json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        ).encode()
        # Rebase through the existing full-provenance project copy machinery.
        # It expects historical paper member names internally, not in the v4
        # transfer payload.
        working = {}
        for name, data in members.items():
            historical = (
                "artifacts/papers/snapshots/"
                + name[len("artifacts/generated_papers/.snapshots/") :]
                if name.startswith("artifacts/generated_papers/.snapshots/")
                else "artifacts/papers/" + name[len("artifacts/generated_papers/") :]
                if name.startswith("artifacts/generated_papers/")
                else name
            )
            working[historical] = data
        session_ids: dict[str, str] = {}
        rebased = rebase_copy(
            project_bundle.portable_bundle(working),
            source_id=old_id,
            new_id=new_id,
            source_path="/sigma-import-original",
            destination_path=str(destination),
            session_ids_out=session_ids,
            preserve_project_identity=preserve_identity and not independent,
        )
        members = project_bundle._decode(rebased)
        # Imported sessions retain their immediate source identity for audit.
        # Preserve saved findings and their original status, including stopped.
        for old_session_id, new_session_id in session_ids.items():
            member = f"research-sessions/{new_session_id}.json"
            if member not in members:
                raise BundleError("Imported session checkpoint is missing")
            record = json.loads(members[member])
            record["source_session_id"] = old_session_id
            record["imported_via_bundle"] = True
            members[member] = (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode(
                "utf-8"
            )
        members = {_canon(name): data for name, data in members.items()}
    # Verify all paper artifacts before publishing the directory.
    historical = {}
    for name, data in members.items():
        legacy = (
            "artifacts/papers/snapshots/" + name[len("artifacts/generated_papers/.snapshots/") :]
            if name.startswith("artifacts/generated_papers/.snapshots/")
            else "artifacts/papers/" + name[len("artifacts/generated_papers/") :]
            if name.startswith("artifacts/generated_papers/")
            else name
        )
        historical[legacy] = data
    project_bundle._verify_imported_papers(historical)
    project_bundle.restore(project_bundle.stored_bundle(members), destination)
    return destination
