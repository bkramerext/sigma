"""User-owned model connection adapter for explicitly local authenticated workspaces."""

from __future__ import annotations

from sigma.openai_connection import AuthContext

UNAVAILABLE_GUIDANCE = "Personal ChatGPT authentication is unavailable in hosted SIGMA. Choose a configured sponsor or continue with saved research."


async def auth_context(subject_hash: str | None) -> AuthContext:
    """Load the current local user's own credentials; never use these on hosted services."""
    from sigma import chatgpt_auth, cloud_auth

    if subject_hash is None:
        return AuthContext(
            token="",
            mode="chatgpt",
            status="unavailable",
            identity="cloud_personal_unavailable:unbound",
        )
    if not cloud_auth.config().local:
        from sigma import personal_browser, personal_inference

        if personal_browser.enabled():
            try:
                state = await personal_inference.account()
                if state["status"] == "verified":
                    binding = state["binding"]
                    return AuthContext(
                        token="",
                        mode="chatgpt",
                        status="connected",
                        identity=f"cloud_personal_worker:{subject_hash}:{binding}",
                        account_label=state["account_label"],
                        transport="personal_worker",
                        worker_binding=binding,
                    )
            except personal_inference.PersonalInferenceUnavailable:
                pass
        return AuthContext(
            token="",
            mode="chatgpt",
            status="unavailable",
            identity="cloud_personal_unavailable:" + subject_hash,
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
