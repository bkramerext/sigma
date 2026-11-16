"""Validate active host-Caddy proxy routes, not comments in a Caddyfile.

The installed host config is first adapted to Caddy's canonical JSON.
Only the two reviewed loopback upstreams are accepted for SIGMA's web host.
"""

from __future__ import annotations

import json
import sys
from typing import Any

EXPECTED = {"127.0.0.1:18081", "127.0.0.1:18082"}
EXPECTED_HOST = "sigma-research.duckdns.org"


class InvalidDirectRouting(ValueError):
    pass


def validate(config: Any) -> None:
    if not isinstance(config, dict):
        raise InvalidDirectRouting("Invalid host Caddy configuration")
    dialed: set[str] = set()

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("handler") == "reverse_proxy":
                upstreams = node.get("upstreams")
                if not isinstance(upstreams, list) or not upstreams:
                    raise InvalidDirectRouting("Unexpected host reverse proxy")
                for upstream in upstreams:
                    if not isinstance(upstream, dict) or not isinstance(
                        upstream.get("dial"), str
                    ):
                        raise InvalidDirectRouting("Unexpected host reverse proxy")
                    dialed.add(upstream["dial"])
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    # Caddy may host other domains. Only routes with an explicit SIGMA host
    # matcher count, and matching endpoints hidden under another hostname
    # cannot trick the deployment guard into removing the working edge.
    try:
        servers = config["apps"]["http"]["servers"]
        if not isinstance(servers, dict):
            raise InvalidDirectRouting("No host Caddy HTTP servers")
        matched = 0
        for server in servers.values():
            for route in server.get("routes", []):
                if any(
                    EXPECTED_HOST in matcher.get("host", [])
                    for matcher in route.get("match", [])
                    if isinstance(matcher, dict)
                ):
                    matched += 1
                    visit(route)
    except (KeyError, TypeError, AttributeError) as exc:
        raise InvalidDirectRouting("Invalid host Caddy HTTP routing") from exc
    if not matched or dialed != EXPECTED:
        raise InvalidDirectRouting(
            "SIGMA host is not routed exclusively to direct loopback ports"
        )


def main() -> None:
    try:
        validate(json.load(sys.stdin))
    except (ValueError, TypeError, KeyError, AttributeError):
        raise SystemExit("Host Caddy direct routing validation failed") from None


if __name__ == "__main__":
    main()
