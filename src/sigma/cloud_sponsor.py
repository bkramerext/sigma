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
from sigma.ai_store import read, sponsor_directory, sponsor_transaction, use_directory
from sigma.projects import ProjectError
from sigma.sponsor_diagnostics import record

_last_issue: tuple[str, float] | None = None


def _diagnose(issue: str | None) -> None:
    """Report a bounded sponsor state to the server log without account secrets."""
    global _last_issue
    if issue is None:
        _last_issue = None
        return
    now = time.monotonic()
    if _last_issue is None or _last_issue[0] != issue or now - _last_issue[1] >= 60:
        record("sponsor_connection", issue)
        _last_issue = (issue, now)


def inference_provider() -> str:
    """Return the provider bound to sponsored inference in this deployment."""
    # Sponsored inference uses the designated ChatGPT account by default in
    # both local and hosted modes. API billing requires explicit operator opt-in.
    return os.environ.get("SIGMA_CLOUD_INFERENCE_PROVIDER", "chatgpt").strip()


def expected_email() -> str:
    email = os.environ.get("SIGMA_CLOUD_SPONSOR_EMAIL", "").strip().casefold()
    if not email:
        from sigma import cloud_auth, cloud_workspaces

        if cloud_auth.config().local and not cloud_workspaces.enabled():
            return cloud_auth.INVITATION_RECIPIENT
    if "@" not in email:
        raise ProjectError("Configure the explicit SIGMA_CLOUD_SPONSOR_EMAIL first.")
    return email


async def sponsor_session() -> dict:
    """Never use API keys or another saved account when sponsor validation fails."""
    try:
        email = expected_email()
        async with sponsor_transaction() as state:
            account_id = _designated_account_id(state, email)
            if account_id is None:
                _diagnose("registration_missing")
                return {"status": "disconnected"}
            account = state["accounts"][account_id]
            missing_credentials = not account.get("access_token") and not account.get(
                "refresh_token"
            )
        with use_directory(sponsor_directory()):
            selected = await chatgpt_auth.session(account_id=account_id)
        if (selected.get("account") or {}).get("email", "").casefold() != email:
            _diagnose("identity_mismatch")
            return {"status": "forbidden"}
        if selected.get("status") == "connected":
            _diagnose(None)
        else:
            _diagnose(
                "credential_missing"
                if missing_credentials
                else "credential_" + str(selected.get("status", "unavailable"))
            )
        return selected
    except ProjectError:
        _diagnose("storage_or_configuration_unavailable")
        return {"status": "unavailable"}


async def sponsor_account_id() -> str:
    """Find the designated account for an administrator's local renewal flow."""
    email = expected_email()
    async with sponsor_transaction() as state:
        account_id = _designated_account_id(state, email)
    if account_id is None:
        raise ProjectError("The designated sponsor account has not been provisioned.")
    return account_id


def _designated_account_id(state: dict, email: str) -> str | None:
    """Prefer a usable duplicate over a stale sponsor registration."""
    matches = [
        key
        for key, account in state["accounts"].items()
        if account.get("email", "").casefold() == email
    ]
    if not matches:
        return None
    return max(
        matches,
        key=lambda key: (
            bool(state["accounts"][key].get("access_token")),
            bool(state["accounts"][key].get("refresh_token")),
            key == state.get("active"),
        ),
    )


async def import_session(source: Path) -> None:
    """Import one owned private SIWC registration after signature/identity validation.

    Run on the VM as the backend user, with writers stopped. Source is transferred
    over SSH, never through the public app. The VM's existing host ID is retained.
    """
    from sigma import cloud_workspaces

    if not cloud_workspaces.enabled() or inference_provider() != "chatgpt":
        raise ProjectError("Sponsor import requires hosted ChatGPT sponsorship.")
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
        async with sponsor_transaction() as state:
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
