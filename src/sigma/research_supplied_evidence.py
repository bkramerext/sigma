"""Durable, bounded content compilation for user-supplied research evidence.

Unlike methodology pointers, supplied URLs must be fetched and read. All
network destinations use the reference fetcher's DNS-pinned public HTTPS
validation, including each redirect. No user-supplied text is an instruction.
"""

from __future__ import annotations

import hashlib
import http.client
import socket
import ssl
import time
from datetime import UTC, datetime
from urllib.parse import urljoin

from sigma import project_evidence, research_reference_content

MAX_REMOTE_BYTES = 12 * 1024 * 1024
MAX_LINK_SECONDS = 10
MAX_EXTRACT = 48000


def _fetch_url(url: str) -> tuple[bytes, str, str]:
    current = url
    for redirect_count in range(3):
        host, host_header, _, path, address_info = research_reference_content._public_endpoint(
            current
        )
        family, socktype, proto, _, address = address_info
        deadline = time.monotonic() + MAX_LINK_SECONDS
        request = (
            f"GET {path} HTTP/1.1\r\nHost: {host_header}\r\n"
            "Accept: application/pdf, text/html, text/plain\r\n"
            "Accept-Encoding: identity\r\nUser-Agent: SIGMA-SuppliedEvidence/1.0\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        with socket.socket(family, socktype, proto) as raw:
            raw.settimeout(MAX_LINK_SECONDS)
            raw.connect(address)
            raw.settimeout(max(0.1, deadline - time.monotonic()))
            with ssl.create_default_context().wrap_socket(raw, server_hostname=host) as secure:
                secure.settimeout(max(0.1, deadline - time.monotonic()))
                secure.sendall(request)
                response = http.client.HTTPResponse(secure)
                response.begin()
                status = response.status
                location = response.getheader("Location")
                if status in {301, 302, 303, 307, 308} and location:
                    if redirect_count == 2:
                        raise ValueError("too_many_redirects")
                    current = urljoin(current, location)
                    continue
                if status != 200:
                    raise ValueError(f"http_{status}")
                if response.getheader("Content-Encoding", "identity").lower() != "identity":
                    raise ValueError("unsupported_compression")
                content_type = (response.getheader("Content-Type") or "").lower().split(";")[0]
                if content_type not in {"application/pdf", "text/plain", "text/html"}:
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
                return bytes(payload), content_type, current
    raise ValueError("redirect_unresolved")


def read_link(url: str) -> dict:
    """Read actual HTTPS document contents, or return a typed failure."""
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
        payload, content_type, resolved = _fetch_url(url)
        if content_type == "application/pdf":
            if not payload.startswith(b"%PDF-"):
                raise ValueError("invalid_pdf")
            pages, text, truncated = project_evidence._extract(payload)
            result["pages"] = pages
        else:
            decoded = payload.decode("utf-8", errors="replace")
            if content_type == "text/html":
                parser = research_reference_content._ReadableHTML()
                parser.feed(decoded)
                text = parser.text()
            else:
                text = decoded
            truncated = len(text) > MAX_EXTRACT
            text = text[:MAX_EXTRACT]
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
    except (ValueError, OSError, TimeoutError, ssl.SSLError, http.client.HTTPException) as exc:
        result["reason"] = str(exc)[:160] or type(exc).__name__
    return result


def compile_entry(path: str, entry: dict) -> dict:
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
            return {
                **entry,
                "status": "retrieved",
                "pages": pages,
                "excerpt": text,
                "excerpt_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "incomplete_extract": truncated,
                "reason": None,
            }
        except (ValueError, OSError, project_evidence.ProjectError) as exc:
            return {**entry, "status": "unavailable", "reason": str(exc)[:160], "excerpt": ""}
    if entry["id"].startswith("uploaded-link:"):
        return {
            **entry,
            **read_link(entry["url"]),
            "provenance": "User-supplied external document; extracted assertions are unverified.",
        }
    return {**entry, "status": "unavailable", "reason": "unsupported_source_type"}
