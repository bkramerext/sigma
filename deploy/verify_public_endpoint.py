#!/usr/bin/env python3
"""Read-only production DNS, TLS, SPA and API acceptance probe."""

from sigma.public_endpoint import main

if __name__ == "__main__":
    raise SystemExit(main())
