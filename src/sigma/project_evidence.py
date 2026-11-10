"""Project-scoped, immutable PDF evidence with bounded page-cited extracts."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pypdfium2

from sigma.projects import ProjectError, inspect_project, project_path, project_write_lock

MAX_PDF_BYTES = 12 * 1024 * 1024
MAX_FILES = 20
MAX_EXTRACT_CHARS = 48000
MANIFEST = "artifacts/evidence/manifest.json"
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
    if file.is_symlink():
        raise ProjectError("Evidence storage must not be a symlink.")
    return file.read_bytes() if file.is_file() else None


def _write(path: str, updates: dict[str, bytes | None]) -> None:
    target = project_path(path)
    if target.suffix == ".json":
        from sigma.project_bundle import update_files

        update_files(target, updates)
        return
    from sigma.projects import _stage

    for member, payload in updates.items():
        file = target / member
        if file.is_symlink() or file.parent.is_symlink():
            raise ProjectError("Unsafe evidence storage path.")
        if payload is None:
            file.unlink(missing_ok=True)
            continue
        file.parent.mkdir(parents=True, exist_ok=True)
        stage = _stage(file.parent, payload)
        try:
            os.replace(stage, file)
        finally:
            stage.unlink(missing_ok=True)


def list_evidence(path: str) -> list[dict]:
    inspect_project(path)
    raw = _read(path, MANIFEST)
    if raw is None:
        return []
    rows = json.loads(raw)
    if not isinstance(rows, list):
        raise ProjectError("Evidence manifest is invalid.")
    return rows


def _extract(pdf: bytes) -> tuple[int, str, bool]:
    """Bounded, representative page text from beginning, middle and end."""
    try:
        document = pypdfium2.PdfDocument(pdf)
    except (ValueError, TypeError, RuntimeError) as exc:
        raise ProjectError("PDF cannot be inspected.") from exc
    chunks: list[str] = []
    total = 0
    omitted = False
    try:
        page_count = len(document)
        if not page_count:
            raise ProjectError("PDF has no pages.")
        if page_count > 1000:
            raise ProjectError("PDF exceeds the 1,000-page evidence safety bound.")
        if page_count <= 24:
            indices = list(range(page_count))
        else:
            indices = sorted(
                set(range(8))
                | set(range(max(8, page_count // 2 - 4), min(page_count, page_count // 2 + 4)))
                | set(range(page_count - 8, page_count))
            )
            omitted = True
        for number in indices:
            page = document[number]
            try:
                textpage = page.get_textpage()
                try:
                    # Extract at most 2,000 characters per sampled page.
                    full_page_text = textpage.get_text_range()
                    excerpt = full_page_text[:2000]
                    if len(full_page_text) > len(excerpt):
                        omitted = True
                finally:
                    textpage.close()
            finally:
                page.close()
            if not excerpt.strip():
                continue
            remaining = MAX_EXTRACT_CHARS - total
            if remaining <= 0:
                omitted = True
                break
            excerpt = excerpt[:remaining]
            chunks.append(f"[PDF page {number + 1}]\\n{excerpt}")
            total += len(excerpt)
            if len(excerpt) >= remaining:
                omitted = True
                break
        return page_count, "\\n\\n".join(chunks), omitted
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
        rows = list_evidence(path)
        duplicate = next((row for row in rows if row["sha256"] == sha), None)
        if duplicate is not None:
            return duplicate
        if len(rows) >= MAX_FILES:
            raise ProjectError("This project already has 20 evidence files.")
        identifier = uuid4().hex
        entry = {
            "id": identifier,
            "filename": name,
            "sha256": sha,
            "bytes": len(pdf),
            "pages": page_count,
            "extract_truncated": omitted,
            "uploaded_at": datetime.now(UTC).isoformat(),
            "uploaded_by": principal.email if principal is not None else None,
        }
        updates = {
            f"artifacts/evidence/{identifier}.pdf": pdf,
            f"artifacts/evidence/{identifier}.txt": extract.encode("utf-8"),
            MANIFEST: json.dumps([*rows, entry], sort_keys=True).encode(),
        }
        _write(path, updates)
        return entry


def get_pdf(path: str, identifier: str) -> tuple[dict, bytes]:
    row = next((row for row in list_evidence(path) if row["id"] == identifier), None)
    if row is None:
        raise ProjectError("Evidence file not found.")
    pdf = _read(path, f"artifacts/evidence/{identifier}.pdf")
    if pdf is None or hashlib.sha256(pdf).hexdigest() != row["sha256"]:
        raise ProjectError("Evidence PDF is unavailable or has changed.")
    return row, pdf


def remove_evidence(path: str, identifier: str) -> None:
    with project_write_lock(path):
        rows = list_evidence(path)
        entry = next((row for row in rows if row["id"] == identifier), None)
        if entry is None:
            raise ProjectError("Evidence file not found.")
        from sigma import cloud_auth, project_collaboration

        principal = cloud_auth.current_principal()
        if principal is not None:
            owner = project_collaboration.summary(path)["owner"]
            if principal.role == "guest" or (
                principal.email != owner and principal.email != entry.get("uploaded_by")
            ):
                raise ProjectError("Only the uploader or project owner can remove evidence.")
        _write(
            path,
            {
                f"artifacts/evidence/{identifier}.pdf": None,
                f"artifacts/evidence/{identifier}.txt": None,
                MANIFEST: json.dumps(
                    [row for row in rows if row["id"] != identifier], sort_keys=True
                ).encode(),
            },
        )


def evidence_context(path: str, *, limit: int = 16000) -> list[dict]:
    """Source-attributed extracts, distributing context fairly across files."""
    rows = list_evidence(path)
    output: list[dict] = []
    if not rows:
        return output
    remaining = limit
    for index, row in enumerate(rows):
        body = _read(path, f"artifacts/evidence/{row['id']}.txt")
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
