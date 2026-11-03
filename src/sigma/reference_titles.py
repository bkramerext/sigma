"""Safe, bounded webpage-title lookup for Project Types reference hyperlinks.

No redirects, proxy use, credentials, private-address access or unbounded reads.
Resolution is presentation-only: failures never block saving references.
"""

from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from functools import lru_cache
from html.parser import HTMLParser
from urllib.parse import quote, urlsplit

_MAX_HTML = 65_536
_TIMEOUT = 2.5


class _TitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.og_title: str | None = None
        self.title_parts: list[str] = []
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            data = {key.casefold(): value for key, value in attrs if value is not None}
            if data.get("property", "").casefold() == "og:title":
                self.og_title = data.get("content")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)


def _clean_title(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = " ".join(value.split())
    cleaned = "".join(char for char in cleaned if char.isprintable())
    return cleaned[:180] or None


def _fetch_title(url: str) -> str | None:
    if len(url) > 2048 or any(ord(c) < 32 for c in url):
        return None
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return None
    if parts.username is not None or parts.password is not None:
        return None
    host = parts.hostname.encode("idna").decode("ascii")
    if not host or any(
        char not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for char in host.lower()
    ):
        return None
    port = parts.port or (443 if parts.scheme == "https" else 80)
    # Validate every returned address, not just the one we will use.
    candidates = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not candidates or any(
        not ipaddress.ip_address(address[4][0]).is_global for address in candidates
    ):
        return None
    family, socktype, protocol, _, address = candidates[0]
    path = quote(parts.path or "/", safe="/%:@!$&'()*+,;=-._~")
    if parts.query:
        path += "?" + quote(parts.query, safe="/?%:@!$&'()*+,;=-._~")
    host_header = host if port in {80, 443} else f"{host}:{port}"
    request = (
        f"GET {path} HTTP/1.1\r\nHost: {host_header}\r\n"
        "Accept: text/html\r\nAccept-Encoding: identity\r\n"
        "User-Agent: SIGMA-ReferenceTitles/1.0\r\nConnection: close\r\n\r\n"
    )
    with socket.socket(family, socktype, protocol) as raw:
        raw.settimeout(_TIMEOUT)
        raw.connect(address)  # Pinned, prevalidated IP: no DNS rebinding.
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
                return None  # Never follow redirects.
            if "text/html" not in response.getheader("Content-Type", "").lower():
                return None
            document = response.read(_MAX_HTML + 1)
            if len(document) > _MAX_HTML:
                document = document[:_MAX_HTML]
    parser = _TitleParser()
    parser.feed(document.decode("utf-8", errors="replace"))
    return _clean_title(parser.og_title) or _clean_title("".join(parser.title_parts))


def domain_status(url: str) -> str:
    """Verify an HTTPS/HTTP reference host without fetching arbitrary URLs.

    "invalid" is reserved for malformed, unsafe or definitely nonexistent
    domains. Transient resolver errors are "unverified" and must not erase
    a user's reference. Never follow redirects or contact private addresses.
    """
    try:
        if len(url) > 2048 or any(ord(char) < 32 for char in url):
            return "invalid"
        parts = urlsplit(url)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
        ):
            return "invalid"
        host = parts.hostname.encode("idna").decode("ascii").lower()
        if (
            "." not in host
            or any(
                not label
                or len(label) > 63
                or label.startswith("-")
                or label.endswith("-")
                or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in label)
                for label in host.split(".")
            )
        ):
            return "invalid"
        try:
            if not ipaddress.ip_address(host).is_global:
                return "invalid"
        except ValueError:
            pass
        port = parts.port or (443 if parts.scheme == "https" else 80)
        candidates = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        if not candidates or any(
            not ipaddress.ip_address(address[4][0]).is_global for address in candidates
        ):
            return "invalid"
        return "valid"
    except socket.gaierror as exc:
        # NXDOMAIN is definitive. Timeout or resolver downtime is not.
        if exc.errno == socket.EAI_NONAME or exc.errno == getattr(socket, "EAI_NODATA", None):
            return "invalid"
        return "unverified"
    except (OSError, ValueError, UnicodeError):
        return "unverified"


@lru_cache(maxsize=512)
def resolve_title(url: str) -> str | None:
    try:
        return _fetch_title(url)
    except (OSError, ValueError, UnicodeError, ssl.SSLError, http.client.HTTPException):
        return None
