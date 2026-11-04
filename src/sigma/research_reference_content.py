"""Bounded, SSRF-safe snapshots of project-type research-reference pages.

Snapshots are methodological guidance, not independent validation or subject
evidence. Failed retrieval is explicit and never replaced by invented contents.
"""

from __future__ import annotations

import hashlib
import http.client
import ipaddress
import socket
import ssl
import time
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit

_MAX_URL_LENGTH = 2048
_MAX_RESPONSE_BYTES = 192_000
_MAX_EXCERPT_CHARS = 3200
_TIMEOUT_SECONDS = 3.0
_MAX_REDIRECTS = 2
_SKIPPED_TAGS = {"script", "style", "noscript", "svg", "nav", "header", "footer", "form"}


class _ReadableHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self._main = 0
        self._body: list[str] = []
        self._primary: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIPPED_TAGS:
            self._skip += 1
        if tag in {"main", "article"}:
            self._main += 1
        if tag in {"p", "li", "h1", "h2", "h3", "h4", "section", "br"}:
            self.handle_data("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED_TAGS:
            self._skip = max(0, self._skip - 1)
        if tag in {"main", "article"}:
            self._main = max(0, self._main - 1)

    def handle_data(self, data: str) -> None:
        if not self._skip and data.strip():
            self._body.append(data)
            if self._main:
                self._primary.append(data)

    def text(self) -> str:
        primary = " ".join(self._primary)
        body = primary if len(primary) > 200 else " ".join(self._body)
        return " ".join(body.split())


def _public_endpoint(url: str) -> tuple[str, str, int, str, tuple]:
    if len(url) > _MAX_URL_LENGTH or any(ord(char) < 32 for char in url):
        raise ValueError("invalid_url")
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("non_https_or_credential_url")
    host = parts.hostname.encode("idna").decode("ascii").lower()
    if not host or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for char in host):
        raise ValueError("invalid_host")
    try:
        port = parts.port or 443
    except ValueError as exc:
        raise ValueError("invalid_port") from exc
    if port != 443:
        raise ValueError("nonstandard_port")
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise OSError("dns_failed") from exc
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("private_or_unroutable_address")
    path = quote(parts.path or "/", safe="/%:@!$&'()*+,;=-._~")
    if parts.query:
        path += "?" + quote(parts.query, safe="/?%:@!$&'()*+,;=-._~")
    return host, host, port, path, addresses[0]


def _read_remote(url: str) -> tuple[int, str, bytes, str | None]:
    host, host_header, _port, path, address_info = _public_endpoint(url)
    family, socktype, proto, _, address = address_info
    deadline = time.monotonic() + _TIMEOUT_SECONDS
    request = (
        f"GET {path} HTTP/1.1\r\nHost: {host_header}\r\n"
        "Accept: text/html, text/plain\r\nAccept-Encoding: identity\r\n"
        "User-Agent: SIGMA-ResearchReferences/1.0\r\nConnection: close\r\n\r\n"
    ).encode("ascii")
    with socket.socket(family, socktype, proto) as raw:
        raw.settimeout(_TIMEOUT_SECONDS)
        raw.connect(address)  # DNS result pinned to verified public IP.
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("reference_deadline_exceeded")
        raw.settimeout(remaining)
        with ssl.create_default_context().wrap_socket(raw, server_hostname=host) as secure:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("reference_deadline_exceeded")
            secure.settimeout(remaining)
            secure.sendall(request)
            response = http.client.HTTPResponse(secure)
            response.begin()
            status = response.status
            kind = (response.getheader("Content-Type") or "").lower()
            redirect = response.getheader("Location")
            if status != 200:
                return status, kind, b"", redirect
            if response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("unsupported_compression")
            if "text/html" not in kind and "text/plain" not in kind:
                raise ValueError("unsupported_media_type")
            # read1() performs a bounded single underlying read. A malicious
            # server trickling bytes cannot repeatedly reset an idle timeout
            # to hold the session creation endpoint indefinitely.
            payload = bytearray()
            while len(payload) <= _MAX_RESPONSE_BYTES:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("reference_deadline_exceeded")
                secure.settimeout(remaining)
                chunk = response.read1(min(16_384, _MAX_RESPONSE_BYTES + 1 - len(payload)))
                if not chunk:
                    break
                payload.extend(chunk)
            if len(payload) > _MAX_RESPONSE_BYTES:
                raise ValueError("response_too_large")
            return status, kind, bytes(payload), None


def freeze_reference_content(url: str) -> dict[str, object]:
    """Return a bounded, verifiable exact-content excerpt or an honest failure."""
    result: dict[str, object] = {
        "status": "unavailable",
        "url": url,
        "retrieved_at": None,
        "content_sha256": None,
        "excerpt_sha256": None,
        "excerpt": None,
        "reason": None,
    }
    current = url
    try:
        for attempt in range(_MAX_REDIRECTS + 1):
            status, content_type, payload, redirect = _read_remote(current)
            if status in {301, 302, 303, 307, 308} and redirect:
                if attempt == _MAX_REDIRECTS:
                    raise ValueError("too_many_redirects")
                current = urljoin(current, redirect)
                continue
            if status != 200:
                raise ValueError(f"http_{status}")
            document = payload.decode("utf-8", errors="replace")
            if "text/html" in content_type:
                parser = _ReadableHTML()
                parser.feed(document)
                text = parser.text()
            else:
                text = " ".join(document.split())
            if len(text) < 80:
                raise ValueError("insufficient_readable_content")
            excerpt = text[:_MAX_EXCERPT_CHARS]
            if current != url:
                result["requested_url"] = url
            result.update(
                status="retrieved",
                url=current,
                content_type=content_type.split(";")[0],
                retrieved_at=datetime.now(UTC).isoformat(),
                content_sha256=hashlib.sha256(payload).hexdigest(),
                excerpt_sha256=hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
                excerpt=excerpt,
                excerpt_truncated=len(text) > len(excerpt),
                response_bytes=len(payload),
                reason=None,
            )
            return result
        raise ValueError("redirect_unresolved")
    except (OSError, ValueError, UnicodeError, ssl.SSLError, http.client.HTTPException) as exc:
        result["reason"] = str(exc)[:120] or type(exc).__name__
        return result
