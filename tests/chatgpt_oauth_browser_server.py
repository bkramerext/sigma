"""Local API fixture with external ChatGPT boundaries replaced for browser tests."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

from sigma import chatgpt_auth, openai_connection

_SCOPES = sorted(chatgpt_auth.PLAN_SCOPES | {"openid", "profile", "email", "offline_access"})


async def _discovery() -> dict:
    return chatgpt_auth.EXPECTED_ENDPOINTS | {
        "authorization_endpoint": chatgpt_auth.ISSUER + "/api/accounts/authorize"
    }


async def _http(method: str, url: str, data: dict | None = None) -> tuple[int, dict]:
    if method == "POST" and url == chatgpt_auth.EXPECTED_ENDPOINTS["token_endpoint"]:
        code = (data or {}).get("code", "refresh")
        return 200, {
            "token_type": "Bearer",
            "access_token": "fixture-access-" + code,
            "refresh_token": "fixture-refresh-" + code,
            "id_token": "fixture-id-" + code,
            "expires_in": 3600,
            "scope": " ".join(_SCOPES),
        }
    if method == "POST" and url == chatgpt_auth.EXPECTED_ENDPOINTS["revocation_endpoint"]:
        return 200, {}
    raise AssertionError(f"Unexpected external ChatGPT request: {method} {url}")


async def _validate(
    raw: dict, client_id: str, nonce: str | None, previous: dict | None, host: str
) -> dict:
    return {
        "issuer": chatgpt_auth.ISSUER,
        "subject": "same-chatgpt-subject-z",
        "client_id": client_id,
        "email": "zetacontinuation@gmail.com",
        "name": "Z ChatGPT",
        "ext_agent_host_id": host,
        "access_token": raw["access_token"],
        "refresh_token": raw["refresh_token"],
        "id_token": raw["id_token"],
        "token_type": "Bearer",
        "expires_at": time.time() + 3600,
        "earliest_refresh_at": 0,
        "scopes": list(_SCOPES),
        "saved_at": datetime.now(UTC).isoformat(),
    }


async def _check(key: str, mode: str = "api_key") -> dict:
    # The token value is a test sentinel only. Log routing, never credentials.
    import asyncio
    import os

    def append_audit() -> None:
        path = Path(os.environ["SIGMA_TEST_PROVIDER_AUDIT"])
        path.write_text(path.read_text(encoding="utf-8") + f"{mode}:{key}\n", encoding="utf-8")

    await asyncio.to_thread(append_audit)
    result = {
        "status": "connected",
        "checked_at": datetime.now(UTC).isoformat(),
        "ttl_seconds": 3600,
    }
    openai_connection._cached = result
    openai_connection._at = time.monotonic()
    openai_connection._known = set(openai_connection.CATALOG)
    return result


chatgpt_auth.discovery = _discovery
chatgpt_auth.http = _http
chatgpt_auth.validate_tokens = _validate
openai_connection._check = _check

from sigma import api

app = api.app
