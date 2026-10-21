"""Bounded, coalesced, non-generating authentication/model discovery."""

import asyncio
import hashlib
import json
import os
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from sigma.model_catalog import CATALOG, DEFAULT_MODEL

TTL = 60
RETRY_COOLDOWN = 3
TIMEOUT = 8
MAX_BYTES = 1000000
_cached: dict[str, Any] | None = None
_at = 0.0
_identity = ""
_pending: asyncio.Task | None = None
_known: set[str] = set()
MESSAGES = {
    "connected": (
        "OpenAI API connected",
        "API authentication/reachability verified only. This does not verify selected-model generation, credits, quota or billing.",
    ),
    "unconfigured": (
        "OpenAI API not configured",
        "Set SIGMA_AI_ENABLED=1 and OPENAI_API_KEY in the local server environment, then restart SIGMA. Manual work remains available.",
    ),
    "unauthorized": (
        "Can't connect to OpenAI API · Check API key",
        "OpenAI rejected API authentication (401). Check the server's OPENAI_API_KEY.",
    ),
    "forbidden": (
        "OpenAI API access denied",
        "OpenAI denied key/account permissions (403). Check account and API-key permissions.",
    ),
    "limited": (
        "OpenAI API rate/quota limited",
        "OpenAI returned 429. Check API rate limits or quota/billing; this is not evidence of an invalid key.",
    ),
    "unavailable": (
        "OpenAI API unavailable",
        "Check the server connection or try again. Provider/network/timeout failure; credentials have not been judged invalid.",
    ),
    "invalid_response": (
        "OpenAI API status unknown",
        "OpenAI returned an invalid or oversized model list. Authentication could not be verified safely.",
    ),
}


def _result(status: str, checked: str | None) -> dict[str, Any]:
    label, guidance = MESSAGES[status]
    return {
        "status": status,
        "label": label,
        "guidance": guidance,
        "checked_at": checked,
        "ttl_seconds": TTL,
    }


async def _check(key: str) -> dict[str, Any]:
    global _cached, _at, _known
    status = "unavailable"
    try:
        async with (
            asyncio.timeout(TIMEOUT),
            httpx.AsyncClient(timeout=TIMEOUT, trust_env=False, follow_redirects=False) as client,
            client.stream(
                "GET",
                "https://api.openai.com/v1/models",
                headers={"Authorization": "Bearer " + key},
            ) as response,
        ):
            if response.status_code == 200:
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_BYTES:
                        raise ValueError()
                raw = json.loads(data)
                if (
                    not isinstance(raw, dict)
                    or raw.get("object") != "list"
                    or not isinstance(raw.get("data"), list)
                    or len(raw["data"]) > 10000
                ):
                    raise ValueError()
                ids = set()
                for model in raw["data"]:
                    if (
                        not isinstance(model, dict)
                        or not isinstance(model.get("id"), str)
                        or not 1 <= len(model["id"]) <= 200
                    ):
                        raise ValueError()
                    ids.add(model["id"])
                _known = ids & set(CATALOG)
                status = "connected"
            else:
                status = {401: "unauthorized", 403: "forbidden", 429: "limited"}.get(
                    response.status_code, "unavailable"
                )
    except (TimeoutError, httpx.HTTPError):
        status = "unavailable"
    except (ValueError, TypeError):
        status = "invalid_response"
    _cached = _result(status, datetime.now(UTC).isoformat())
    _at = time.monotonic()
    return dict(_cached)


async def connection(refresh: bool = False) -> dict[str, Any]:
    global _identity, _pending, _cached, _known
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    enabled = os.environ.get("SIGMA_AI_ENABLED") == "1"
    identity = hashlib.sha256((str(enabled) + key).encode()).hexdigest()
    if identity != _identity:
        if _pending and not _pending.done():
            _pending.cancel()
            await asyncio.gather(_pending, return_exceptions=True)
        _identity, _cached, _known, _pending = identity, None, set(), None
    if not enabled or not key:
        return _result("unconfigured", None)
    age = time.monotonic() - _at
    if _cached and age < (RETRY_COOLDOWN if refresh else TTL):
        return dict(_cached)
    if _pending is None or _pending.done():
        _pending = asyncio.create_task(_check(key))
    return dict(await asyncio.shield(_pending))


async def models(refresh: bool = False) -> dict[str, Any]:
    state = await connection(refresh)
    verified = state["status"] == "connected"
    choices = [
        {
            "id": identifier,
            **capability,
            "availability": ("available" if identifier in _known else "unavailable")
            if verified
            else "unverified",
        }
        for identifier, capability in CATALOG.items()
    ]
    accessible = [c["id"] for c in choices if c["availability"] == "available"]
    default = DEFAULT_MODEL if DEFAULT_MODEL in accessible or not accessible else accessible[0]
    message = "Account access checked; generation/billing is not verified."
    if not accessible:
        message = "No reviewed model is verified accessible. Sol/High is an unverified offline preference; manual research remains available."
    elif default != DEFAULT_MODEL:
        message = f"Sol is unavailable to this account. Initial choice: {CATALOG[default]['label']} / High. Later requests never substitute models."
    if os.environ.get("SIGMA_AI_MODEL") and os.environ["SIGMA_AI_MODEL"] not in CATALOG:
        message += " SIGMA_AI_MODEL is not a reviewed reasoning model; legacy projects use the documented Sol/High default. Saved project choices are unaffected."
    return {
        "models": choices,
        "connection": state,
        "default_model": default,
        "default_effort": "high",
        "default_verified": verified and bool(accessible),
        "message": message,
    }
