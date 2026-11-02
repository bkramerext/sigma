"""Read publication guidance exclusively from the project's resolved type references.

Publication guides are editorial instructions, never scientific evidence. Fetching
an untrusted reference URL must not expose loopback, private or metadata services.
"""

from __future__ import annotations

import asyncio
import hashlib
import http.client
import ipaddress
import json
import re
import socket
import ssl
from collections.abc import Awaitable, Callable, Mapping
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote, urlsplit

import pypdfium2

MAX_HTML_BYTES = 256_000
MAX_PDF_BYTES = 4_000_000
MAX_SELECTED = 3
MAX_EXCERPT_CHARS = 3_500
_CACHE: dict[str, str] = {}


class _Paragraphs(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts: list[str] = []
        self.depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "nav", "footer", "header", "svg"}:
            self.skip += 1
        if tag in {"p", "li", "h1", "h2", "h3", "h4"} and not self.skip:
            self.depth += 1
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "footer", "header", "svg"}:
            self.skip = max(0, self.skip - 1)
        if tag in {"p", "li", "h1", "h2", "h3", "h4"} and not self.skip:
            self.depth = max(0, self.depth - 1)

    def handle_data(self, data: str) -> None:
        if self.depth and not self.skip:
            self.parts.append(data)


def readable(text: str, *, html: bool = False) -> str | None:
    """Return only substantial, readable manuscript-guidance text."""
    if html:
        parser = _Paragraphs()
        try:
            parser.feed(text)
        except (ValueError, AssertionError):
            return None
        text = " ".join(parser.parts)
    result = re.sub(r"\s+", " ", text).strip()
    if len(result) < 450 or any(
        marker in result[:700].casefold()
        for marker in ("access denied", "verify you are human", "captcha required")
    ):
        return None
    return result[:MAX_EXCERPT_CHARS]


def _pdf_excerpt(document: bytes) -> str | None:
    """Extract real selectable text without executing content or interpreting links."""
    try:
        pdf = pypdfium2.PdfDocument(document)
        try:
            chunks: list[str] = []
            for index in range(min(len(pdf), 12)):
                page = pdf[index]
                try:
                    textpage = page.get_textpage()
                    try:
                        chunks.append(textpage.get_text_range())
                    finally:
                        textpage.close()
                finally:
                    page.close()
                if sum(len(chunk) for chunk in chunks) > 6_000:
                    break
            return readable(" ".join(chunks))
        finally:
            pdf.close()
    except (ValueError, RuntimeError, OSError):
        return None


def _valid_public_url(url: str) -> bool:
    """Reject credentials, control characters, unsafe ports and IP literals."""
    if len(url) > 2_048 or any(ord(char) < 33 for char in url):
        return False
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 80, 443)
        ):
            return False
        host = parsed.hostname.encode("idna").decode("ascii").casefold()
    except (ValueError, UnicodeError):
        return False
    if not host or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for char in host):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return len(host) <= 253 and all(
            0 < len(label) <= 63 and not label.startswith("-") and not label.endswith("-")
            for label in host.split(".")
        )


def _fetch_blocking(url: str) -> str | None:
    """Pin a verified public DNS address; reject redirects and oversized responses."""
    if not _valid_public_url(url):
        return None
    parts = urlsplit(url)
    host = (parts.hostname or "").encode("idna").decode("ascii")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        return None
    family, socktype, proto, _, address = addresses[0]
    path = quote(parts.path or "/", safe="/%:@!$&'()*+,;=-._~")
    if parts.query:
        path += "?" + quote(parts.query, safe="/?%:@!$&'()*+,;=-._~")
    request = (
        f"GET {path} HTTP/1.1\r\nHost: {host}\r\n"
        "Accept: text/html, text/plain, application/pdf\r\n"
        "Accept-Encoding: identity\r\n"
        "User-Agent: SIGMA-PublicationMethods/1.0\r\n"
        "Connection: close\r\n\r\n"
    )
    with socket.socket(family, socktype, proto) as raw:
        raw.settimeout(2.5)
        raw.connect(address)
        connection = (
            ssl.create_default_context().wrap_socket(raw, server_hostname=host)
            if parts.scheme == "https"
            else raw
        )
        with connection:
            connection.sendall(request.encode("ascii"))
            response = http.client.HTTPResponse(connection)
            response.begin()
            if response.status != 200:
                return None  # Never follow redirects, including to private networks.
            kind = response.getheader("Content-Type", "").lower()
            pdf_content = "application/pdf" in kind or parts.path.lower().endswith(".pdf")
            max_bytes = MAX_PDF_BYTES if pdf_content else MAX_HTML_BYTES
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                return None
    if pdf_content:
        return _pdf_excerpt(body)
    if "text/html" in kind:
        return readable(body.decode("utf-8", errors="replace"), html=True)
    if "text/plain" in kind:
        return readable(body.decode("utf-8", errors="replace"))
    return None


async def _fetch(url: str) -> str | None:
    if not _valid_public_url(url):
        return None
    cached = _CACHE.get(url)
    if cached is not None:
        return cached
    try:
        result = await asyncio.wait_for(asyncio.to_thread(_fetch_blocking, url), timeout=3.0)
    except (
        OSError,
        ValueError,
        UnicodeError,
        RuntimeError,
        TimeoutError,
        http.client.HTTPException,
    ):
        return None
    if result is not None:
        _CACHE[url] = result  # Do not permanently cache missing/temporarily blocked material.
    return result


def _references(project: Mapping[str, Any]) -> list[dict[str, str]]:
    """Use the frozen effective type references, which already include common/ancestors."""
    raw = project.get("publication_references", [])
    if not isinstance(raw, list):
        return []
    output: list[dict[str, str]] = []
    urls: set[str] = set()
    for item in raw[:100]:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        name = item.get("name")
        if not isinstance(url, str) or not _valid_public_url(url) or url in urls:
            continue
        if not isinstance(name, str) or not name.strip():
            name = url
        output.append({"title": name[:200], "url": url})
        urls.add(url)
    return output


def _reference_fingerprint(references: list[dict[str, str]]) -> str:
    return hashlib.sha256(
        json.dumps(references, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def _reusable(
    previous: list[dict[str, Any]],
    references: list[dict[str, str]],
    kind: str,
) -> bool:
    if not previous or not 1 <= len(previous) <= min(MAX_SELECTED, len(references)):
        return False
    official = {item["url"]: item["title"] for item in references}
    reference_sha = _reference_fingerprint(references)
    chosen_urls: set[str] = set()
    for item in previous:
        if not isinstance(item, dict):
            return False
        url = item.get("url")
        excerpt = item.get("excerpt")
        if (
            not isinstance(url, str)
            or url not in official
            or url in chosen_urls
            or item.get("title") != official[url]
            or item.get("type") != kind
            or item.get("reference_set_sha256") != reference_sha
            or not isinstance(excerpt, str)
            or len(excerpt) < 450
            or hashlib.sha256(excerpt.encode()).hexdigest() != item.get("sha256")
        ):
            return False
        chosen_urls.add(url)
    return True


async def select(
    project: Mapping[str, Any],
    previous: list[dict[str, Any]] | None = None,
    *,
    fetch: Callable[[str], Awaitable[str | None]] = _fetch,
) -> tuple[list[dict[str, Any]], str]:
    """Select only readable official publication references; no catalog fallback."""
    references = _references(project)
    kind = str(project.get("investigation_type") or "default")
    if previous and _reusable(previous, references, kind):
        return previous, "reused"
    selected: list[dict[str, Any]] = []
    # The resolved list includes common and specialized entries. Prefer one
    # specialized reference when identifiable, retaining the full official set.
    try:
        from sigma import project_types

        common_urls = {
            ref["url"]
            for ref in project_types.common_references()["publication_standards_references"]
        }
    except (KeyError, OSError, ValueError):
        common_urls = set()
    priority = sorted(references, key=lambda item: item["url"] in common_urls)
    reference_sha = _reference_fingerprint(references)
    for item in priority:
        if len(selected) == MAX_SELECTED:
            break
        url = item["url"]
        try:
            body = await asyncio.wait_for(fetch(url), timeout=3.0)
        except (
            OSError,
            ValueError,
            UnicodeError,
            RuntimeError,
            TimeoutError,
            http.client.HTTPException,
        ):
            continue
        excerpt = readable(body) if isinstance(body, str) else None
        if excerpt is None:
            continue
        selected.append(
            {
                "title": item["title"],
                "url": url,
                "tier": "general" if url in common_urls else "discipline",
                "type": kind,
                "branch": "project_type",
                "excerpt": excerpt,
                "sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
                "reference_set_sha256": reference_sha,
            }
        )
    return selected, "selected" if selected else "unavailable"


def prompt_material(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Untrusted source prose may guide writing, never supply research evidence."""
    return [
        {
            "title": str(item["title"]),
            "url": str(item["url"]),
            "scope": str(item["tier"]),
            "writing_guidance_excerpt": str(item["excerpt"]),
        }
        for item in items[:MAX_SELECTED]
    ]
