"""User-owned model connection adapter for explicitly local authenticated workspaces."""

from __future__ import annotations

from sigma.openai_connection import AuthContext

UNAVAILABLE_GUIDANCE = "Personal ChatGPT authentication is unavailable in hosted SIGMA. Choose a configured sponsor or continue with saved research."


def has_durable_plan_authorization(subject: str) -> bool:
    """Whether this Google subject has completed personal OAuth with plan scopes."""
    from sigma import ai_store, chatgpt_auth, cloud_auth

    if not cloud_auth.config().local:
        return False
    try:
        state = ai_store.read(ai_store.personal_directory_for_subject(subject) / "credentials.json")
        active = state.get("active")
        account = state.get("accounts", {}).get(active) if isinstance(active, str) else None
        scopes = account.get("scopes", []) if isinstance(account, dict) else []
        return bool(
            state.get("mode") == "chatgpt"
            and isinstance(account, dict)
            and isinstance(account.get("subject"), str)
            and isinstance(account.get("client_id"), str)
            and bool(account.get("access_token") or account.get("refresh_token"))
            and chatgpt_auth.PLAN_SCOPES.issubset(scopes)
            and account.get("plan_authorized", True) is True
        )
    except (OSError, RuntimeError, ValueError, TypeError):
        return False


async def auth_context(subject_hash: str | None) -> AuthContext:
    """Load the current local user's own credentials; never use these on hosted services."""
    from sigma import chatgpt_auth, cloud_auth

    if subject_hash is None or not cloud_auth.config().local:
        return AuthContext(
            token="",
            mode="chatgpt",
            status="unavailable",
            identity="cloud_personal_unavailable:" + (subject_hash or "unbound"),
        )
    selected = await chatgpt_auth.session()
    mode = selected.get("mode", "chatgpt")
    if mode == "api_key":
        token = await chatgpt_auth.api_key_token()
        return AuthContext(
            token=token or "",
            mode="api_key",
            status="connected" if token else "unconfigured",
            identity=f"cloud_personal_api_key:{subject_hash}",
        )
    account = selected.get("account") or {}
    return AuthContext(
        token=account.get("access_token", ""),
        mode="chatgpt",
        status=selected.get("status", "disconnected"),
        identity=f"cloud_personal_chatgpt:{subject_hash}:{selected.get('account_id') or 'none'}",
        account_label=account.get("email") or account.get("name"),
    )
