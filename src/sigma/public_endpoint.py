#!/usr/bin/env python3
"""Read-only DNS, redirect, TLS, SPA and API acceptance probe for a live release."""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import sys
import urllib.error
import urllib.request
from collections.abc import Callable


def resolve_ipv4(hostname: str) -> set[str]:
    """Return IPv4 answers from the host resolver, failing on lookup errors."""
    return {
        str(answer[4][0])
        for answer in socket.getaddrinfo(
            hostname, 443, family=socket.AF_INET, type=socket.SOCK_STREAM
        )
    }


def require_private_ports_closed(ipv4: str) -> None:
    """Confirm known app/daemon ports cannot be reached at the public IP."""
    for port in (8000, 5173, 2375, 2376):
        try:
            connection = socket.create_connection((ipv4, port), timeout=2)
        except OSError:
            continue
        connection.close()
        raise ValueError(f"unexpected public TCP listener on port {port}")


def response(
    url: str, *, opener: Callable[..., object] = urllib.request.urlopen
) -> tuple[int, dict[str, str], bytes]:
    """Fetch without following redirects so unexpected routing is visible."""
    request = urllib.request.Request(url, headers={"User-Agent": "SIGMA-public-check/1"})
    try:
        result = opener(request, context=ssl.create_default_context(), timeout=10)
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers.items()), error.read(4096)
    with result:  # type: ignore[attr-defined]
        return result.status, dict(result.headers.items()), result.read(65536)  # type: ignore[attr-defined]


def validate_public_endpoint(
    hostname: str,
    expected_ipv4: str,
    *,
    resolver: Callable[[str], set[str]] = resolve_ipv4,
    fetch: Callable[[str], tuple[int, dict[str, str], bytes]] | None = None,
    check_private_ports: Callable[[str], None] = require_private_ports_closed,
) -> list[str]:
    """Return safe PASS checks or raise ValueError with a non-sensitive reason."""
    if not hostname or any(
        ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-"
        for ch in hostname
    ):
        raise ValueError("hostname format is invalid")
    try:
        expected = socket.inet_aton(expected_ipv4)
    except OSError as error:
        raise ValueError("expected IPv4 address is invalid") from error
    if socket.inet_ntoa(expected) != expected_ipv4:
        raise ValueError("expected IPv4 address is invalid")

    addresses = resolver(hostname)
    if addresses != {expected_ipv4}:
        raise ValueError("DNS A record does not resolve only to the expected static IPv4")
    check_private_ports(expected_ipv4)

    get = fetch or (lambda url: response(url))
    status, headers, _ = get(f"http://{hostname}/")
    location = headers.get("Location", headers.get("location", ""))
    if status not in {301, 308} or location != f"https://{hostname}/":
        raise ValueError("HTTP root does not redirect to the canonical HTTPS root")

    status, _, _ = get(f"https://{hostname}/")
    if status != 200:
        raise ValueError("HTTPS application root did not return 200")
    status, _, _ = get(f"https://{hostname}/projects/deep-link-check")
    if status != 200:
        raise ValueError("HTTPS SPA deep link did not return 200")
    status, _, body = get(f"https://{hostname}/api/cloud-auth/status")
    if status != 200:
        raise ValueError("HTTPS API status route did not return 200")
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("HTTPS API status route returned invalid JSON") from error
    if (
        not isinstance(payload, dict)
        or payload.get("enabled") is not True
        or payload.get("ready") is not True
        or payload.get("target") != "hosted"
    ):
        raise ValueError("HTTPS API status does not report ready hosted authentication")
    return [
        "DNS A record",
        "private backend and daemon ports",
        "HTTP to HTTPS redirect",
        "HTTPS certificate and root",
        "SPA deep link",
        "same-origin hosted API",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hostname", default="sigma-research.duckdns.org")
    parser.add_argument("--expected-ip", required=True, help="owner-verified reserved static IPv4")
    arguments = parser.parse_args(argv)
    try:
        checks = validate_public_endpoint(arguments.hostname, arguments.expected_ip)
    except (OSError, TimeoutError, ValueError, urllib.error.URLError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    for check in checks:
        print(f"PASS: {check}")
    print("Public endpoint checks passed. No DNS, cloud, or application state was changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
