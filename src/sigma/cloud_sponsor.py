"""Explicitly provisioned ChatGPT sponsor session, isolated from local accounts."""

import argparse
import asyncio
import os
import secrets
import time
from pathlib import Path

import httpx
import jwt

from sigma import chatgpt_auth
from sigma.ai_store import read, transaction
from sigma.projects import ProjectError


def expected_email() -> str:
    email = os.environ.get("SIGMA_CLOUD_SPONSOR_EMAIL", "").strip().casefold()
    if not email or "@" not in email:
        raise ProjectError("Configure the explicit SIGMA_CLOUD_SPONSOR_EMAIL first.")
    return email


async def sponsor_session() -> dict:
    """Never use API keys or another saved account when sponsor validation fails."""
    try:
        email = expected_email()
        async with transaction() as state:
            account = state["accounts"].get(state["active"]) or {}
            if state["mode"] != "chatgpt" or account.get("email", "").casefold() != email:
                return {"status": "disconnected"}
        selected = await chatgpt_auth.session()
        if (selected.get("account") or {}).get("email", "").casefold() != email:
            return {"status": "forbidden"}
        return selected
    except ProjectError:
        return {"status": "unavailable"}


async def import_session(source: Path) -> None:
    """Import one owned private SIWC registration after signature/identity validation.

    Run on the VM as the backend user, with writers stopped. Source is transferred
    over SSH, never through the public app. The VM's existing host ID is retained.
    """
    from sigma import cloud_workspaces

    if (
        not cloud_workspaces.enabled()
        or os.environ.get("SIGMA_CLOUD_INFERENCE_PROVIDER") != "chatgpt"
    ):
        raise ProjectError("Sponsor import requires explicit hosted ChatGPT configuration.")
    email = expected_email()
    if not source.is_absolute():
        raise ProjectError("Use an absolute path to the protected credential file.")
    try:
        imported = read(source)
        account = imported["accounts"][imported["active"]]
        if imported["mode"] != "chatgpt" or account["client_id"] == "dynamic_agent_client":
            raise ValueError()
        claims = await chatgpt_auth.verify_id(account["id_token"], account["client_id"], None)
        if (
            claims.get("email_verified") is not True
            or claims.get("email", "").casefold() != email
            or claims["sub"] != account["subject"]
            or account.get("email", "").casefold() != email
            or account.get("issuer") != chatgpt_auth.ISSUER
            or account.get("token_type", "").lower() != "bearer"
            or not chatgpt_auth.PLAN_SCOPES.issubset(account["scopes"])
            or not time.time() + 60 < account["expires_at"] <= time.time() + 86400
            or any(
                not isinstance(account.get(key), str) or not 1 <= len(account[key]) <= 32000
                for key in ("access_token", "refresh_token", "id_token")
            )
        ):
            raise ValueError()
        async with transaction() as state:
            # Store only the selected sponsor, not other laptop registrations.
            account = dict(account, ext_agent_host_id=state["ext_agent_host_id"])
            identifier = secrets.token_urlsafe(18)
            state["accounts"] = {identifier: account}
            state["active"], state["mode"] = identifier, "chatgpt"
    except (ValueError, KeyError, TypeError) as exc:
        raise ProjectError("Sponsor import rejected; existing credentials were retained.") from exc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import protected sponsor SIWC credentials on the VM"
    )
    parser.add_argument("credential_file", type=Path)
    args = parser.parse_args()
    try:
        asyncio.run(import_session(args.credential_file))
    except (
        ProjectError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        httpx.HTTPError,
        jwt.PyJWTError,
        chatgpt_auth.AuthFailure,
    ):
        # Never print provider errors, token values, or file contents.
        parser.exit(1, "Sponsor import failed; verify private file, account, scopes and expiry.\n")
    print("Sponsor session imported. Stop using the source copy; the VM owns refreshes.")


if __name__ == "__main__":
    main()
