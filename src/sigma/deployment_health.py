"""Credential-free readiness probe for the hosted container stack."""

from __future__ import annotations

import asyncio
import subprocess
import sys

from sigma import cloud_auth, cloud_research, openai_connection, python_sandbox


def main() -> int:
    from sigma.storage import validate_startup

    try:
        validate_startup()
    except RuntimeError:
        return 1
    auth = cloud_auth.config()
    if not auth.enabled or auth.error:
        return 1
    try:
        cloud_research._spend_ceiling_decimal()
        cloud_research._user_spend_ceiling_decimal()
        credential = asyncio.run(openai_connection.sponsored_auth_context("deployment-health"))
        if not openai_connection.cloud_credential(credential):
            return 1
        subprocess.run(
            ["docker", "info", "--format={{.ServerVersion}}"],
            check=True,
            capture_output=True,
            timeout=20,
            env=python_sandbox._runtime_environment(),
        )
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
