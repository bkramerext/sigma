"""Validate active host-Caddy proxy routes, not comments in a Caddyfile.

The installed host config is first adapted to Caddy's canonical JSON.
Only the two reviewed loopback upstreams are accepted for SIGMA's web host.
"""
from __future__ import annotations

import json
import sys
from typing import Any

EXPECTED = {"127.0.0.1:18081", "127.0.0.1:18082"}


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
                    if not isinstance(upstream, dict) or not isinstance(upstream.get("dial"), str):
                        raise InvalidDirectRouting("Unexpected host reverse proxy")
                    dialed.add(upstream["dial"])
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(config.get("apps", {}).get("http", {}))
    if dialed != EXPECTED:
        raise InvalidDirectRouting("Host Caddy is not routing exclusively to SIGMA loopback ports")


def main() -> None:
    try:
        validate(json.load(sys.stdin))
    except (ValueError, TypeError, KeyError, AttributeError):
        raise SystemExit("Host Caddy direct routing validation failed") from None


if __name__ == "__main__":
    main()
