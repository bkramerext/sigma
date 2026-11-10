"""Project-scoped, immutable PDF evidence with bounded page-cited extracts."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import pypdfium2

from sigma.projects import ProjectError, inspect_project, project_path, project_write_lock

MAX_PDF_BYTES = 12 * 1024 * 1024
MAX_FILES = 20
MAX_EXTRACT_CHARS = 512_000
MANIFEST = "artifacts/source_material/manifest.json"
_NAME = re.compile(r"[^\w .()\-]", re.UNICODE)


def _name(value: str) -> str:
    name = _NAME.sub("_", Path(value.replace("\\", "/")).name).strip(" .")
    if not name or len(name) > 120:
        raise ProjectError("Evidence filename must be 1–120 characters.")
    if not name.lower().endswith(".pdf"):
        raise ProjectError("Only PDF evidence is supported.")
    return name


def _read(path: str, member: str) -> bytes | None:
    target = project_path(path)
    if target.suffix == ".json":
        from sigma.project_bundle import list_files, read_file

        return read_file(target, member) if member in list_files(target) else None
    file = target / member
    ancestor = file
    while ancestor != target:
        if ancestor.is_symlink():
            raise ProjectError("Evidence storage must not be a symlink.")
        ancestor = ancestor.parent
    return file.read_bytes() if file.is_file() else None


def _write(path: str, updates: dict[str, bytes | None]) -> None:
    target = project_path(path)
    if target.suffix == ".json":
        from sigma.project_bundle import update_files

        update_files(target, updates)
        return
    from sigma.projects import _stage

    ordered = list(updates.items())
    if any(payload is None for _, payload in ordered):
        # Publish the *manifest removal* first. A crash may leave unreferenced
        # blobs, but never a manifest pointing to a deleted source.
        ordered.sort(key=lambda item: item[0] != MANIFEST)
    else:
        # Publish immutable payloads before the manifest entry that names them.
        ordered.sort(key=lambda item: item[0] == MANIFEST)
    for member, payload in ordered:
        file = target / member
        # Reject symlinked ancestors as well as the final destination.
        ancestor = file
        while ancestor != target:
            if ancestor.is_symlink():
                raise ProjectError("Unsafe evidence storage path.")
            ancestor = ancestor.parent
        if payload is None:
            file.unlink(missing_ok=True)
            continue
        file.parent.mkdir(parents=True, exist_ok=True)
        stage = _stage(file.parent, payload)
        try:
            os.replace(stage, file)
        finally:
            stage.unlink(missing_ok=True)


def _file_rows(path: str) -> list[dict]:
    inspect_project(path)
    raw = _read(path, MANIFEST)
    if raw is None:
        return []
    rows = json.loads(raw)
    if not isinstance(rows, list):
        raise ProjectError("Evidence manifest is invalid.")
    return rows


def list_evidence(path: str) -> list[dict]:
    """Combine URL records from project.json with disk-backed file records."""
    view = inspect_project(path)
    return sorted(
        [*_file_rows(path), *view.project.source_material_links],
        key=lambda row: (
            row.get("kind") == "link",
            str(row.get("uploaded_at") or ""),
        ),
    )


def has_enabled_evidence(path: str) -> bool:
    return any(row.get("enabled", True) for row in list_evidence(path))


def _extract(pdf: bytes) -> tuple[int, str, bool]:
    """Read every page, preserving page boundaries; reject incomplete extraction.

    The document must fit the bounded text safety limit. Silent sampling or
    truncation would cause the agents to mistake unseen premises for facts.
    """
    try:
        document = pypdfium2.PdfDocument(pdf)
    except (ValueError, TypeError, RuntimeError) as exc:
        raise ProjectError("PDF cannot be inspected.") from exc
    chunks: list[str] = []
    total = 0
    try:
        page_count = len(document)
        if not page_count:
            raise ProjectError("PDF has no pages.")
        if page_count > 1000:
            raise ProjectError("PDF exceeds the 1,000-page evidence safety bound.")
        for number in range(page_count):
            page = document[number]
            try:
                textpage = page.get_textpage()
                try:
                    extracted = textpage.get_text_range()
                finally:
                    textpage.close()
            finally:
                page.close()
            if not extracted.strip():
                raise ProjectError(
                    f"Page {number + 1} has no extractable text; scanned PDFs need OCR."
                )
            total += len(extracted)
            if total > MAX_EXTRACT_CHARS:
                raise ProjectError(
                    "Source Material exceeds the 512,000-character extraction limit; "
                    "split the document into smaller attachments."
                )
            chunks.append(f"[PDF page {number + 1}]\n{extracted}")
        return page_count, "\n\n".join(chunks), False
    finally:
        document.close()


def add_evidence(path: str, filename: str, pdf: bytes) -> dict:
    name = _name(filename)
    if not 5 <= len(pdf) <= MAX_PDF_BYTES or not pdf.startswith(b"%PDF-"):
        raise ProjectError("Expected a valid PDF up to 12 MiB.")
    page_count, extract, omitted = _extract(pdf)
    if not extract.strip():
        raise ProjectError("PDF has no extractable text. Scanned-image OCR is not supported yet.")
    sha = hashlib.sha256(pdf).hexdigest()
    from sigma import cloud_auth

    principal = cloud_auth.current_principal()
    if principal is not None and principal.role == "guest":
        raise ProjectError("Guests cannot add evidence.")
    with project_write_lock(path):
        rows = _file_rows(path)
        duplicate = next((row for row in rows if row.get("sha256") == sha), None)
        if duplicate is not None:
            return duplicate
        if len(rows) + len(inspect_project(path).project.source_material_links) >= MAX_FILES:
            raise ProjectError("This project already has 20 Source Material entries.")
        identifier = uuid4().hex
        entry = {
            "id": identifier,
            "kind": "file",
            "filename": name,
            "enabled": True,
            "sha256": sha,
            "bytes": len(pdf),
            "pages": page_count,
            "extract_truncated": omitted,
            "uploaded_at": datetime.now(UTC).isoformat(),
            "uploaded_by": principal.email if principal is not None else None,
        }
        updates: dict[str, bytes | None] = {
            f"artifacts/source_material/{identifier}.pdf": pdf,
            f"artifacts/source_material/{identifier}.txt": extract.encode("utf-8"),
            MANIFEST: json.dumps([*rows, entry], sort_keys=True).encode(),
        }
        _write(path, updates)
        return entry


def _validated_link_url(url: str) -> str:
    """Validate using the same domain resolver as Research/Publication Standards."""
    from sigma.reference_titles import domain_status

    canonical = url.strip()
    try:
        parsed = urlsplit(canonical)
        port = parsed.port
    except (ValueError, UnicodeError) as exc:
        raise ProjectError("Enter a valid public website address, such as example.org.") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or len(canonical) > 2048
        or any(ord(char) < 32 for char in canonical)
    ):
        raise ProjectError("Enter a valid public HTTP or HTTPS website address.")
    standard_port = 443 if parsed.scheme == "https" else 80
    if port not in {None, standard_port}:
        raise ProjectError("Source Material URLs must use the standard HTTP or HTTPS port.")
    if domain_status(canonical) == "invalid":
        raise ProjectError("Website could not be found. Check the address.")
    # Unverified DNS is not definitive failure, as with Research/Publication Standards.
    return canonical


def _require_source_editor() -> None:
    from sigma import cloud_auth

    principal = cloud_auth.current_principal()
    if principal is not None and principal.role == "guest":
        raise ProjectError("Guests cannot modify Source Material.")


def add_link(path: str, url: str) -> dict:
    """Store HTTP/HTTPS Source Material links in project.json."""
    from sigma import cloud_auth
    from sigma.projects import _update_project

    _require_source_editor()
    canonical = _validated_link_url(url)
    principal = cloud_auth.current_principal()
    new_entry = {
        "id": uuid4().hex,
        "kind": "link",
        "url": canonical,
        "enabled": True,
        "uploaded_by": principal.email if principal else None,
        "uploaded_at": datetime.now(UTC).isoformat(),
    }
    selected = new_entry

    def update(project):
        nonlocal selected
        for item in project.source_material_links:
            if item["url"] == canonical:
                selected = item
                return project
        if len(project.source_material_links) + len(_file_rows(path)) >= MAX_FILES:
            raise ProjectError("This project already has 20 Source Material entries.")
        return replace(
            project,
            source_material_links=(*project.source_material_links, new_entry),
        )

    _update_project(path, update)
    return selected


def edit_link(path: str, identifier: str, url: str, *, expected_url: str | None = None) -> dict:
    """Edit a linked source without changing its ID, uploader, or enabled status."""
    from sigma.projects import _update_project

    _require_source_editor()
    canonical = _validated_link_url(url)
    selected: dict = {}

    def update(project):
        nonlocal selected
        rows = project.source_material_links
        current = next((row for row in rows if row["id"] == identifier), None)
        if current is None:
            raise ProjectError("Source Material link not found.")
        if expected_url is not None and current["url"] != expected_url:
            raise ProjectError("Source Material was changed by another collaborator. Your edit was not saved.")
        if any(row["url"] == canonical and row["id"] != identifier for row in rows):
            raise ProjectError("Duplicate Source Material URL.")
        selected = {**current, "url": canonical}
        return replace(
            project,
            source_material_links=tuple(
                selected if row["id"] == identifier else row for row in rows
            ),
        )

    _update_project(path, update)
    return selected


def set_enabled(path: str, identifier: str, enabled: bool) -> dict:
    """Persist enable/disable for both links and attachments."""
    from sigma.projects import _update_project

    _require_source_editor()
    if type(enabled) is not bool:
        raise ProjectError("Source Material enabled state must be boolean.")
    if any(row["id"] == identifier for row in inspect_project(path).project.source_material_links):
        selected: dict = {}

        def update(project):
            nonlocal selected
            rows = project.source_material_links
            current = next((row for row in rows if row["id"] == identifier), None)
            if current is None:
                raise ProjectError("Source Material link not found.")
            selected = {**current, "enabled": enabled}
            return replace(
                project,
                source_material_links=tuple(
                    selected if row["id"] == identifier else row for row in rows
                ),
            )

        _update_project(path, update)
        return selected
    with project_write_lock(path):
        rows = _file_rows(path)
        current = next((row for row in rows if row["id"] == identifier), None)
        if current is None:
            raise ProjectError("Source Material attachment not found.")
        selected = {**current, "enabled": enabled}
        updated = [selected if row["id"] == identifier else row for row in rows]
        _write(path, {MANIFEST: json.dumps(updated, sort_keys=True).encode()})
        return selected


def get_pdf(path: str, identifier: str) -> tuple[dict, bytes]:
    row = next((row for row in list_evidence(path) if row["id"] == identifier), None)
    if row is None:
        raise ProjectError("Evidence file not found.")
    if row.get("kind") == "link":
        raise ProjectError("Evidence link is not an attached PDF.")
    pdf = _read(path, f"artifacts/source_material/{identifier}.pdf")
    if pdf is None or hashlib.sha256(pdf).hexdigest() != row["sha256"]:
        raise ProjectError("Evidence PDF is unavailable or has changed.")
    return row, pdf


def remove_evidence(path: str, identifier: str) -> None:
    from sigma.projects import _update_project

    # Authorized collaborators edit shared project Source Material together.
    # Project path resolution and the write guard enforce membership; guest
    # accounts remain read-only even for entries they previously uploaded.
    _require_source_editor()

    if any(
        item["id"] == identifier for item in inspect_project(path).project.source_material_links
    ):

        def update(project):
            entry = next(
                (row for row in project.source_material_links if row["id"] == identifier),
                None,
            )
            if entry is None:
                raise ProjectError("Source Material link not found.")
            return replace(
                project,
                source_material_links=tuple(
                    row for row in project.source_material_links if row["id"] != identifier
                ),
            )

        _update_project(path, update)
        return

    with project_write_lock(path):
        rows = _file_rows(path)
        entry = next((row for row in rows if row["id"] == identifier), None)
        if entry is None:
            raise ProjectError("Source Material file not found.")
        _write(
            path,
            {
                f"artifacts/source_material/{identifier}.pdf": None,
                f"artifacts/source_material/{identifier}.txt": None,
                MANIFEST: json.dumps(
                    [row for row in rows if row["id"] != identifier], sort_keys=True
                ).encode(),
            },
        )


def evidence_context(path: str, *, limit: int = 16000) -> list[dict]:
    """Source-attributed extracts, distributing context fairly across files."""
    rows = [row for row in list_evidence(path) if row.get("enabled", True)]
    output: list[dict] = []
    if not rows:
        return output
    remaining = limit
    for index, row in enumerate(rows):
        if row.get("kind") == "link":
            output.append(
                {
                    "id": f"uploaded-link:{row['id']}",
                    "url": row["url"],
                    "excerpt": "",
                    "incomplete_extract": True,
                    "provenance": "User-supplied URL pointer; content has not been retrieved or verified.",
                }
            )
            continue
        body = _read(path, f"artifacts/source_material/{row['id']}.txt")
        if body is None:
            raise ProjectError("Saved evidence extract is missing.")
        text = body.decode("utf-8")
        allowance = max(0, remaining // (len(rows) - index))
        excerpt = text[:allowance]
        remaining -= len(excerpt)
        output.append(
            {
                "id": f"uploaded-pdf:{row['id']}",
                "filename": row["filename"],
                "sha256": row["sha256"],
                "pages": row["pages"],
                "excerpt": excerpt,
                "incomplete_extract": row["extract_truncated"] or len(excerpt) < len(text),
                "provenance": "User-supplied document; claims are unverified source assertions.",
            }
        )
    return output
