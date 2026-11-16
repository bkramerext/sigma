"""Fail-closed validation of the active SIGMA host-Caddy direct routes.

Inspect the *adapted* Caddy JSON rather than trusting comments or snippets.
Both upstream addresses and their route semantics must match: /api(/...) goes
to SIGMA's backend, while the unmatched frontend handler goes to Nginx.
Other domains are allowed and ignored.
"""

from __future__ import annotations

import json
import sys
from typing import Any

EXPECTED_HOST = "sigma-research.duckdns.org"
API_PATHS = frozenset({"/api", "/api/*"})
BACKEND = "127.0.0.1:18081"
FRONTEND = "127.0.0.1:18082"


class InvalidDirectRouting(ValueError):
    pass


def validate(config: Any) -> None:
    if not isinstance(config, dict):
        raise InvalidDirectRouting("Invalid host Caddy configuration")

    # A 'match' clause is a list of OR alternatives; each matcher contains
    # ANDed conditions. For this dedicated proxy we accept only the exact API
    # path matcher or an unconditional frontend fallback.
    seen: list[tuple[frozenset[str] | None, str]] = []

    def visit(node: Any, active_path: frozenset[str] | None = None) -> None:
        if isinstance(node, dict):
            matchers = node.get("match")
            if matchers is not None:
                if not isinstance(matchers, list) or not matchers:
                    raise InvalidDirectRouting("Malformed Caddy route matchers")
                paths: list[frozenset[str]] = []
                for matcher in matchers:
                    if not isinstance(matcher, dict):
                        raise InvalidDirectRouting("Malformed Caddy route matcher")
                    if "path" in matcher:
                        raw = matcher["path"]
                        if (
                            not isinstance(raw, list)
                            or not raw
                            or not all(isinstance(p, str) for p in raw)
                        ):
                            raise InvalidDirectRouting("Malformed API path matcher")
                        paths.append(frozenset(raw))
                if paths:
                    if len(paths) != len(matchers) or len(set(paths)) != 1:
                        raise InvalidDirectRouting("Ambiguous API route matchers")
                    if active_path is not None and active_path != paths[0]:
                        raise InvalidDirectRouting("Nested API path matcher changes routing")
                    active_path = paths[0]

            if node.get("handler") == "reverse_proxy":
                upstreams = node.get("upstreams")
                if (
                    not isinstance(upstreams, list)
                    or len(upstreams) != 1
                    or not isinstance(upstreams[0], dict)
                    or not isinstance(upstreams[0].get("dial"), str)
                ):
                    raise InvalidDirectRouting("Unexpected host reverse proxy")
                seen.append((active_path, upstreams[0]["dial"]))
            for key, value in node.items():
                # Recurse through Caddy's nested subroutes; the route's match
                # propagates to handles but must not leak into sibling routes.
                if key not in {"match", "upstreams"}:
                    visit(value, active_path)
        elif isinstance(node, list):
            for value in node:
                visit(value, active_path)

    try:
        servers = config["apps"]["http"]["servers"]
        if not isinstance(servers, dict):
            raise InvalidDirectRouting("No host Caddy HTTP servers")
        matched = 0
        for server in servers.values():
            for route in server.get("routes", []):
                matchers = route.get("match", [])
                if any(
                    isinstance(matcher, dict) and EXPECTED_HOST in matcher.get("host", [])
                    for matcher in matchers
                ):
                    matched += 1
                    visit(route)
    except (KeyError, TypeError, AttributeError) as exc:
        raise InvalidDirectRouting("Invalid host Caddy HTTP routing") from exc

    if matched != 1 or sorted(seen, key=lambda pair: pair[1]) != sorted(
        [(API_PATHS, BACKEND), (None, FRONTEND)], key=lambda pair: pair[1]
    ):
        raise InvalidDirectRouting(
            "SIGMA host does not route /api to backend and other paths to frontend"
        )


def main() -> None:
    try:
        validate(json.load(sys.stdin))
    except (ValueError, TypeError, KeyError, AttributeError):
        raise SystemExit("Host Caddy direct routing validation failed") from None


if __name__ == "__main__":
    main()
