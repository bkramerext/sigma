"""Durable, bounded content compilation for user-supplied research evidence.

Unlike methodology pointers, supplied URLs must be fetched and read. All
network destinations use the reference fetcher's DNS-pinned public HTTP/HTTPS
validation, including each redirect. No user-supplied text is an instruction.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import re
import socket
import ssl
import time
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit

from sigma import project_evidence, research_reference_content
from sigma.projects import project_write_lock

MAX_REMOTE_BYTES = 12 * 1024 * 1024
MAX_LINK_SECONDS = 10
MAX_EXTRACT = project_evidence.MAX_EXTRACT_CHARS
_RETRY_DELAYS_SECONDS = (0.25, 0.75)
_TRANSIENT_HTTP_STATUSES = {408, 425, 429, 500, 502, 503, 504}
_BINARY_PDF_MEDIA_TYPES = {"application/octet-stream", "binary/octet-stream", "application/x-pdf"}
_SUPPORTED_MEDIA_TYPES = {"application/pdf", "text/plain", "text/html"} | _BINARY_PDF_MEDIA_TYPES


def _fetch_url_once(url: str) -> tuple[bytes, str, str]:
    current = url
    deadline = time.monotonic() + MAX_LINK_SECONDS
    for redirect_count in range(3):
        host, host_header, _, path, address_info = research_reference_content._public_endpoint(
            current, allow_http=True
        )
        family, socktype, proto, _, address = address_info
        request = (
            f"GET {path} HTTP/1.1\r\nHost: {host_header}\r\n"
            "Accept: application/pdf, application/octet-stream, text/html, text/plain\r\n"
            "Accept-Encoding: identity\r\nUser-Agent: SIGMA-SuppliedEvidence/1.0\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        with socket.socket(family, socktype, proto) as raw:
            raw.settimeout(max(0.1, deadline - time.monotonic()))
            raw.connect(address)
            raw.settimeout(max(0.1, deadline - time.monotonic()))
            connection = (
                ssl.create_default_context().wrap_socket(raw, server_hostname=host)
                if urlsplit(current).scheme == "https"
                else raw
            )
            with connection as secure:
                secure.settimeout(max(0.1, deadline - time.monotonic()))
                secure.sendall(request)
                response = http.client.HTTPResponse(secure)
                response.begin()
                status = response.status
                location = response.getheader("Location")
                if status in {301, 302, 303, 307, 308} and location:
                    if redirect_count == 2:
                        raise ValueError("too_many_redirects")
                    target = urljoin(current, location)
                    if urlsplit(current).scheme == "https" and urlsplit(target).scheme != "https":
                        raise ValueError("https_redirect_downgrade")
                    current = target
                    continue
                if status != 200:
                    raise ValueError(f"http_{status}")
                if response.getheader("Content-Encoding", "identity").lower() != "identity":
                    raise ValueError("unsupported_compression")
                content_type = (response.getheader("Content-Type") or "").lower().split(";")[0]
                if content_type not in _SUPPORTED_MEDIA_TYPES:
                    raise ValueError("unsupported_media_type")
                declared = response.getheader("Content-Length")
                if declared and int(declared) > MAX_REMOTE_BYTES:
                    raise ValueError("document_too_large")
                payload = bytearray()
                while len(payload) <= MAX_REMOTE_BYTES:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("evidence_fetch_deadline")
                    secure.settimeout(remaining)
                    chunk = response.read1(min(16384, MAX_REMOTE_BYTES + 1 - len(payload)))
                    if not chunk:
                        break
                    payload.extend(chunk)
                if len(payload) > MAX_REMOTE_BYTES:
                    raise ValueError("document_too_large")
                data = bytes(payload)
                # GitHub raw and other file hosts serve valid PDFs with a generic
                # binary media type. Accept only PDF-magic bytes, never arbitrary
                # binary content or an HTML error response posing as a PDF.
                if content_type in _BINARY_PDF_MEDIA_TYPES:
                    if not data.startswith(b"%PDF-"):
                        raise ValueError("binary_response_is_not_pdf")
                    content_type = "application/pdf"
                return data, content_type, current
    raise ValueError("redirect_unresolved")


def _fetch_url(url: str) -> tuple[bytes, str, str]:
    """Bounded retry for transient failures, without retrying invalid sources.

    Every attempt repeats public-IP validation and redirect checks. Definitive
    failures (404, bad media type, invalid URL, TLS errors) fail immediately.
    """
    for attempt in range(len(_RETRY_DELAYS_SECONDS) + 1):
        try:
            return _fetch_url_once(url)
        except (ValueError, OSError, TimeoutError, http.client.HTTPException) as exc:
            if isinstance(exc, ssl.SSLError):
                raise
            retryable = isinstance(exc, (OSError, TimeoutError, http.client.HTTPException))
            if isinstance(exc, ValueError):
                reason = str(exc)
                retryable = any(
                    reason == f"http_{status}" for status in _TRANSIENT_HTTP_STATUSES
                )
            if not retryable or attempt == len(_RETRY_DELAYS_SECONDS):
                raise
            time.sleep(_RETRY_DELAYS_SECONDS[attempt])
    raise AssertionError("unreachable source fetch retry state")


def read_link(url: str, fetched: tuple[bytes, str, str] | None = None) -> dict:
    """Read actual public HTTP/HTTPS content, or return a typed failure."""
    result = {
        "status": "unavailable",
        "url": url,
        "excerpt": "",
        "content_sha256": None,
        "excerpt_sha256": None,
        "reason": None,
        "retrieved_at": None,
        "incomplete_extract": True,
    }
    try:
        payload, content_type, resolved = fetched if fetched is not None else _fetch_url(url)
        if content_type == "application/pdf":
            if not payload.startswith(b"%PDF-"):
                raise ValueError("invalid_pdf")
            pages, text, truncated = project_evidence._extract(payload)
            result["pages"] = pages
        else:
            decoded = payload.decode("utf-8")
            if content_type == "text/html":
                parser = research_reference_content._ReadableHTML()
                parser.feed(decoded)
                text = parser.text()
            else:
                text = decoded
            if len(text) > MAX_EXTRACT:
                raise ValueError("document_exceeds_text_extraction_limit")
            truncated = False
        if not text.strip():
            raise ValueError("no_extractable_text")
        result.update(
            status="retrieved",
            resolved_url=resolved,
            content_type=content_type,
            excerpt=text,
            content_sha256=hashlib.sha256(payload).hexdigest(),
            excerpt_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            retrieved_at=datetime.now(UTC).isoformat(),
            incomplete_extract=truncated,
            reason=None,
        )
    except (
        ValueError, OSError, TimeoutError, ssl.SSLError,
        http.client.HTTPException, project_evidence.ProjectError,
    ) as exc:
        result["reason"] = str(exc)[:160] or type(exc).__name__
    return result


def compile_entry(path: str, entry: dict, session_id: str | None = None) -> dict:
    """Convert a frozen source entry into a content-bearing evidence record."""
    if entry["id"].startswith("uploaded-pdf:"):
        try:
            identifier = entry["id"].split(":", 1)[1]
            metadata, pdf = project_evidence.get_pdf(path, identifier)
            if metadata["sha256"] != entry["sha256"]:
                raise ValueError("attachment_changed_after_session_start")
            pages, text, truncated = project_evidence._extract(pdf)
            if not text.strip():
                raise ValueError("no_extractable_text")
            snapshot_path = None
            if session_id is not None:
                if not re.fullmatch(r"[0-9a-f-]{36}", session_id) or not re.fullmatch(
                    r"[0-9a-f]{32}", identifier
                ):
                    raise ValueError("invalid_source_identity")
                snapshot_path = f"artifacts/source_material/snapshots/{session_id}/{identifier}.pdf"
                with project_write_lock(path):
                    saved = project_evidence._read(path, snapshot_path)
                    if saved is None:
                        project_evidence._write(path, {snapshot_path: pdf})
                    elif hashlib.sha256(saved).hexdigest() != entry["sha256"]:
                        raise ValueError("attachment_snapshot_changed")
            return {
                **entry,
                "status": "retrieved",
                "pages": pages,
                "excerpt": text,
                "excerpt_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "incomplete_extract": truncated,
                "snapshot_path": snapshot_path,
                "reason": None,
            }
        except (ValueError, OSError, project_evidence.ProjectError) as exc:
            return {**entry, "status": "unavailable", "reason": str(exc)[:160], "excerpt": ""}
    if entry["id"].startswith("uploaded-link:"):
        fetched = None
        snapshot = None
        new_fetch = False
        if session_id is not None:
            source_id = entry["id"].split(":", 1)[1]
            if not re.fullmatch(r"[0-9a-f-]{36}", session_id) or not re.fullmatch(
                r"[0-9a-f]{32}", source_id
            ):
                return {**entry, "status": "unavailable", "reason": "invalid_source_identity"}
            snapshot = f"artifacts/source_material/snapshots/{session_id}/{source_id}"
            try:
                metadata = project_evidence._read(path, snapshot + ".json")
                binary = project_evidence._read(path, snapshot + ".bin")
            except (ValueError, OSError) as exc:
                return {**entry, "status": "unavailable", "reason": str(exc)[:160]}
            if metadata is not None and binary is not None:
                try:
                    saved = json.loads(metadata)
                    if (
                        saved["url"] == entry["url"]
                        and saved["sha256"] == hashlib.sha256(binary).hexdigest()
                    ):
                        fetched = (binary, saved["content_type"], saved["resolved_url"])
                except (ValueError, KeyError, TypeError):
                    pass
            if fetched is None:
                try:
                    fetched = _fetch_url(entry["url"])
                    new_fetch = True
                except (
                    ValueError,
                    OSError,
                    TimeoutError,
                    ssl.SSLError,
                    http.client.HTTPException,
                ) as exc:
                    return {**entry, "status": "unavailable", "reason": str(exc)[:160]}
        result = read_link(entry["url"], fetched)
        if new_fetch and result["status"] == "retrieved" and snapshot is not None:
            assert fetched is not None
            binary, content_type, resolved = fetched
            try:
                with project_write_lock(path):
                    project_evidence._write(
                        path,
                        {
                            snapshot + ".bin": binary,
                            snapshot + ".json": json.dumps(
                                {
                                    "url": entry["url"],
                                    "resolved_url": resolved,
                                    "content_type": content_type,
                                    "sha256": hashlib.sha256(binary).hexdigest(),
                                },
                                sort_keys=True,
                            ).encode(),
                        },
                    )
            except (ValueError, OSError) as exc:
                result = {**result, "status": "unavailable", "reason": str(exc)[:160]}
        return {
            **entry,
            **result,
            "snapshot_path": snapshot,
            "provenance": "User-supplied external document; extracted assertions are unverified.",
        }
    return {**entry, "status": "unavailable", "reason": "unsupported_source_type"}
