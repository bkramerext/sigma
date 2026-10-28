"""Documented OSS SIWC: discovery, PKCE/OIDC, loopback, refresh and revocation."""

import asyncio
import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import jwt

from sigma.ai_store import directory, sponsor_directory, transaction, transaction_at
from sigma.projects import ProjectError
from sigma.sponsor_diagnostics import record

ISSUER = "https://auth.openai.com"
RESOURCE = "https://api.openai.com/v1"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
PLAN_SCOPES = {"resource.invoke", "chatgpt.tokens.use.direct"}
USAGE_URL = "https://chatgpt.com/settings/usage"
EXPECTED_ENDPOINTS = {
    "issuer": ISSUER,
    "authorization_endpoint": ISSUER + "/api/accounts/authorize",
    "token_endpoint": ISSUER + "/api/accounts/oauth/token",
    "revocation_endpoint": ISSUER + "/api/accounts/oauth/revoke",
    "jwks_uri": ISSUER + "/.well-known/jwks.json",
}
TERMINAL_REFRESH = {
    "invalid_grant",
    "invalid_refresh_token",
    "token_expired",
    "refresh_token_expired",
    "refresh_token_invalidated",
    "refresh_token_reused",
}


class AuthFailure(Exception):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


async def http(method: str, url: str, data: dict | None = None) -> tuple[int, dict]:
    # Only fixed trusted endpoints; credentials never traverse redirects/proxies.
    async with (
        asyncio.timeout(10),
        httpx.AsyncClient(timeout=8, trust_env=False, follow_redirects=False) as client,
        client.stream(method, url, data=data) as response,
    ):
        raw = bytearray()
        async for chunk in response.aiter_bytes():
            raw.extend(chunk)
            if len(raw) > 1000000:
                raise ValueError()
        value = json.loads(raw) if raw else {}
        if not isinstance(value, dict):
            raise TypeError()
        return response.status_code, value


async def discovery() -> dict:
    code, value = await http("GET", ISSUER + "/.well-known/openid-configuration")
    if code != 200 or any(
        value.get(key) != expected for key, expected in EXPECTED_ENDPOINTS.items()
    ):
        raise AuthFailure(
            "unavailable",
            "OpenAI sign-in discovery is unavailable or changed. Retry later; no credentials were replaced.",
        )
    return value


async def verify_id(token: str, client_id: str, nonce: str | None) -> dict:
    header = jwt.get_unverified_header(token)
    if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
        raise ValueError()
    code, jwks = await http("GET", EXPECTED_ENDPOINTS["jwks_uri"])
    keys = jwks.get("keys")
    if code != 200 or not isinstance(keys, list) or len(keys) > 32:
        raise ValueError()
    matching = [
        key
        for key in keys
        if key.get("kid") == header["kid"]
        and key.get("kty") == "RSA"
        and key.get("use", "sig") == "sig"
    ]
    if len(matching) != 1:
        raise ValueError()
    key = jwt.PyJWK.from_dict(matching[0], algorithm="RS256")
    claims = jwt.decode(
        token,
        key.key,
        algorithms=["RS256"],
        audience=client_id,
        issuer=ISSUER,
        options={"require": ["sub", "iss", "aud", "exp", "iat"]},
    )
    if (
        not isinstance(claims["sub"], str)
        or not claims["sub"]
        or (
            nonce is not None
            and (
                not isinstance(claims.get("nonce"), str)
                or not hmac.compare_digest(claims["nonce"], nonce)
            )
        )
        or (
            isinstance(claims["aud"], list)
            and len(claims["aud"]) > 1
            and claims.get("azp") != client_id
        )
    ):
        raise ValueError()
    return claims


def timestamp(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        return datetime.fromisoformat(value).timestamp()
    raise ValueError()


async def validate_tokens(
    raw: dict, client_id: str, nonce: str | None, previous: dict | None, host: str
) -> dict:
    if raw.get("token_type", "").lower() != "bearer":
        raise ValueError()
    for key in ("access_token", "refresh_token", "id_token"):
        if not isinstance(raw.get(key), str) or not 1 <= len(raw[key]) <= 32000:
            raise ValueError()
    expiry = raw.get("expires_in")
    if not isinstance(expiry, int) or isinstance(expiry, bool) or not 0 < expiry <= 86400:
        raise ValueError()
    if not isinstance(raw.get("scope"), str) or len(raw["scope"]) > 4000:
        raise ValueError()
    if "openid" not in raw["scope"].split():
        raise ValueError()
    claims = await verify_id(raw["id_token"], client_id, nonce)
    if previous and (claims["sub"] != previous["subject"] or client_id != previous["client_id"]):
        raise ValueError()
    now = time.time()
    earliest = (
        timestamp(raw["earliest_refresh_at"]) if raw.get("earliest_refresh_at") is not None else now
    )
    if not 0 <= earliest <= now + 86400:
        raise ValueError()
    return {
        "issuer": ISSUER,
        "subject": claims["sub"],
        "client_id": client_id,
        "email": str(claims.get("email", ""))[:200] if claims.get("email_verified") is True else "",
        "name": str(claims.get("name", "ChatGPT account"))[:100],
        "ext_agent_host_id": host,
        **{
            key: raw[key]
            for key in ("access_token", "refresh_token", "id_token", "token_type", "expires_in")
        },
        "scopes": raw["scope"].split(),
        "expires_at": now + expiry,
        "earliest_refresh_at": earliest,
        "saved_at": datetime.now(UTC).isoformat(),
    }


@dataclass
class Attempt:
    id: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    state: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    nonce: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    verifier: str = field(default_factory=lambda: secrets.token_urlsafe(48))
    account_id: str | None = None
    sponsor: bool = False
    hosted: bool = False
    client_id: str = "dynamic_agent_client"
    redirect_uri: str = ""
    status: str = "connecting"
    message: str = "Complete sign-in in your browser."
    expires: float = field(default_factory=lambda: time.monotonic() + 300)
    server: asyncio.Server | None = None
    retry_client_id: str | None = None
    consumed: bool = False
    task: asyncio.Task | None = None
    timer: asyncio.TimerHandle | None = None


_attempts: dict[str, Attempt] = {}


def finish(attempt: Attempt, status: str, message: str) -> None:
    attempt.status, attempt.message = status, message
    if attempt.sponsor:
        record("sponsor_oauth", status)
    _urls.pop(attempt.id, None)
    if attempt.server:
        attempt.server.close()
    if attempt.timer:
        attempt.timer.cancel()
    # Erase transient proof secrets after the exchange/cancellation.
    attempt.verifier = attempt.nonce = attempt.state = ""


async def begin(
    account_id: str | None = None,
    enable_plan: bool = False,
    retry_attempt_id: str | None = None,
    *,
    sponsor: bool = False,
) -> dict:
    for key, attempt in list(_attempts.items()):
        if time.monotonic() > attempt.expires + 60:
            _attempts.pop(key)
    if sum(a.status == "connecting" for a in _attempts.values()) >= 4:
        raise ProjectError(
            "A sign-in is already pending. Complete or cancel it before another attempt."
        )
    try:
        endpoints = await discovery()
        from sigma import cloud_workspaces

        attempt = Attempt(
            account_id=account_id, sponsor=sponsor, hosted=cloud_workspaces.enabled()
        )
        if retry_attempt_id:
            failed = _attempts.get(retry_attempt_id)
            if (
                not failed
                or failed.account_id != account_id
                or not failed.retry_client_id
                or failed.status != "failed"
                or time.monotonic() > failed.expires
            ):
                raise ProjectError(
                    "Previous sign-in can no longer be retried. Start a new sign-in."
                )
            attempt.client_id = failed.retry_client_id
        async with transaction_at(sponsor_directory() if sponsor else directory()) as state:
            previous = state["accounts"].get(account_id) if account_id else None
            if account_id and not previous:
                raise ProjectError("Saved account was not found. Choose Connect another account.")
            if previous:
                attempt.client_id = previous["client_id"]
            host = state["ext_agent_host_id"]
        attempt.server = await asyncio.start_server(
            lambda reader, writer: callback(attempt, reader, writer), "127.0.0.1", 0, limit=8192
        )
        port = attempt.server.sockets[0].getsockname()[1]
        if attempt.hosted:
            from sigma.cloud_auth import config

            origin = config().origin
            if (
                not origin
                or urlsplit(origin).scheme != "https"
                or urlsplit(origin).path not in ("", "/")
            ):
                raise ProjectError("Hosted ChatGPT callback requires a configured HTTPS public origin.")
            attempt.redirect_uri = origin.rstrip("/") + "/api/ai/auth/callback/" + attempt.id
        else:
            attempt.redirect_uri = f"http://127.0.0.1:{port}/auth/callback"
        _attempts[attempt.id] = attempt
        attempt.timer = asyncio.get_running_loop().call_later(
            300,
            finish,
            attempt,
            "cancelled",
            "Sign-in expired. Retry when ready; existing accounts were retained.",
        )
        params = {
            "client_id": attempt.client_id,
            "ext_agent_host_id": host,
            "response_type": "code",
            "redirect_uri": attempt.redirect_uri,
            "scope": SCOPES,
            "resource": RESOURCE,
            "state": attempt.state,
            "nonce": attempt.nonce,
            "code_challenge_method": "S256",
            "code_challenge": base64.urlsafe_b64encode(
                hashlib.sha256(attempt.verifier.encode()).digest()
            )
            .rstrip(b"=")
            .decode(),
        }
        if previous:
            # Hints stay on the backend; authorization URL is handed off via a local
            # no-store redirect so retained ID tokens never appear in React payloads.
            if previous.get("id_token"):
                params["id_token_hint"] = previous["id_token"]
            if previous.get("email"):
                params["login_hint"] = previous["email"]
        elif attempt.client_id == "dynamic_agent_client":
            params["agent_name_hint"] = "SIGMA"
        if enable_plan:
            params["prompt"] = "consent"
        _urls[attempt.id] = endpoints["authorization_endpoint"] + "?" + urlencode(params)
        if sponsor:
            record("sponsor_oauth", "started")
        return {
            "id": attempt.id,
            "status": attempt.status,
            "authorization_url": "/api/ai/auth/open/" + attempt.id,
        }
    except (httpx.HTTPError, TimeoutError, ValueError, jwt.PyJWTError, AuthFailure):
        raise ProjectError(
            "Cannot start ChatGPT sign-in. OpenAI discovery/network validation failed; retry later."
        ) from None


_urls: dict[str, str] = {}


def attempt_status(identifier: str) -> dict:
    attempt = _attempts.get(identifier)
    if not attempt:
        raise ProjectError(
            "Sign-in attempt expired or belongs to another server session. Retry sign-in."
        )
    if attempt.status == "connecting" and time.monotonic() > attempt.expires:
        cancel(identifier)
    return {
        "id": attempt.id,
        "status": attempt.status,
        "message": attempt.message,
        "retryable": bool(attempt.retry_client_id),
    }


def cancel(identifier: str) -> None:
    attempt = _attempts.get(identifier)
    if attempt and attempt.status == "connecting":
        if attempt.task:
            attempt.task.cancel()
        finish(
            attempt,
            "cancelled",
            "Sign-in cancelled. Your existing account and research were retained.",
        )
    _urls.pop(identifier, None)


def authorization_url(identifier: str) -> str:
    attempt = _attempts.get(identifier)
    if not attempt or attempt.status != "connecting" or attempt.consumed:
        raise ProjectError("Sign-in attempt is no longer active. Retry sign-in.")
    url = _urls.pop(identifier, None)
    if url is None:
        raise ProjectError(
            "The sign-in browser was already opened. Complete it or cancel and retry."
        )
    return url  # Browser handoff can be opened once only.


async def callback(
    attempt: Attempt, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    accepted = False
    try:
        async with asyncio.timeout(20):
            head = await reader.readuntil(b"\r\n\r\n")
            if len(head) > 8192:
                raise ValueError()
            lines = head.decode("ascii").split("\r\n")
            method, target, _version = lines[0].split(" ")
            headers = {}
            for line in lines[1:]:
                if line:
                    key, value = line.split(":", 1)
                    if key.lower() in headers:
                        raise ValueError()
                    headers[key.lower()] = value.strip()
            parsed = urlsplit(target)
            query = parse_qs(parsed.query, strict_parsing=True)
            if (
                method != "GET"
                or parsed.path
                != (
                    "/api/ai/auth/callback/" + attempt.id
                    if attempt.hosted
                    else "/auth/callback"
                )
                or parsed.netloc
                or parsed.scheme
                or headers.get("host") != urlsplit(attempt.redirect_uri).netloc
                or headers.get("origin") not in (None, ISSUER)
                or any(len(values) != 1 for values in query.values())
                or not hmac.compare_digest(query.get("state", [""])[0], attempt.state)
                or not attempt.state
                or attempt.status != "connecting"
                or attempt.consumed
                or time.monotonic() > attempt.expires
            ):
                raise ValueError()
            # No await between single-use check and consumption.
            attempt.consumed = True
            attempt.task = asyncio.current_task()
            accepted = True
            if "error" in query:
                finish(
                    attempt,
                    "declined",
                    "ChatGPT sign-in was declined. Retry sign-in or choose another billing mode.",
                )
            else:
                client_id = query.get("client_id", [attempt.client_id])[0]
                if (
                    not re.fullmatch(r"[a-zA-Z0-9_-]{1,200}", client_id)
                    or client_id == "dynamic_agent_client"
                    or (
                        attempt.client_id != "dynamic_agent_client"
                        and client_id != attempt.client_id
                    )
                ):
                    raise ValueError()
                code = query.get("code", [""])[0]
                if not 1 <= len(code) <= 4000:
                    raise ValueError()
                async with transaction_at(
                    sponsor_directory() if attempt.sponsor else directory()
                ) as state:
                    previous = (
                        state["accounts"].get(attempt.account_id) if attempt.account_id else None
                    )
                    result, raw = await http(
                        "POST",
                        EXPECTED_ENDPOINTS["token_endpoint"],
                        {
                            "grant_type": "authorization_code",
                            "client_id": client_id,
                            "code": code,
                            "code_verifier": attempt.verifier,
                            "redirect_uri": attempt.redirect_uri,
                            "resource": RESOURCE,
                        },
                    )
                    if result != 200:
                        if raw.get("error") == "invalid_grant":
                            attempt.retry_client_id = client_id
                        raise AuthFailure(
                            "failed",
                            "ChatGPT code exchange failed. Retry sign-in; existing credentials were retained.",
                        )
                    record = await validate_tokens(
                        raw, client_id, attempt.nonce, previous, state["ext_agent_host_id"]
                    )
                    if attempt.sponsor:
                        from sigma.cloud_sponsor import expected_email

                        if record["email"].casefold() != expected_email():
                            raise AuthFailure(
                                "failed", "ChatGPT sponsor identity does not match designated administrator."
                            )
                    # Same issued client must remain bound to its verified subject.
                    existing = next(
                        (
                            (key, value)
                            for key, value in state["accounts"].items()
                            if value["client_id"] == client_id
                        ),
                        None,
                    )
                    if existing and existing[1]["subject"] != record["subject"]:
                        raise ValueError()
                    if attempt.status != "connecting":
                        raise ValueError()
                    identifier = attempt.account_id or (
                        existing[0] if existing else secrets.token_urlsafe(18)
                    )
                    state["accounts"][identifier] = record
                    state["active"], state["mode"] = identifier, "chatgpt"
                permitted = PLAN_SCOPES.issubset(record["scopes"])
                finish(
                    attempt,
                    "connected" if permitted else "plan_not_permitted",
                    "ChatGPT connected. Return to SIGMA."
                    if permitted
                    else "Signed in; ChatGPT plan permission was not granted. Enable plan use or choose another billing mode.",
                )
    except asyncio.CancelledError:
        if accepted:
            finish(attempt, "cancelled", "Sign-in cancelled; no new account was activated.")
    except (
        ValueError,
        KeyError,
        TypeError,
        UnicodeError,
        jwt.PyJWTError,
        AuthFailure,
        ProjectError,
        httpx.HTTPError,
        TimeoutError,
        asyncio.IncompleteReadError,
        asyncio.LimitOverrunError,
    ):
        if accepted:
            finish(
                attempt,
                "failed",
                "ChatGPT sign-in validation failed. Retry; existing accounts were retained.",
            )
    finally:
        # Never reflect code/state/token/provider error or log the request target.
        body = b"Return to SIGMA to continue. You can close this sign-in tab."
        try:
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: text/plain; charset=utf-8\r\nCache-Control: no-store\r\nReferrer-Policy: no-referrer\r\nContent-Security-Policy: default-src 'none'\r\nConnection: close\r\nContent-Length: "
                + str(len(body)).encode()
                + b"\r\n\r\n"
                + body
            )
            await writer.drain()
        except (OSError, ConnectionError):
            pass
        writer.close()
        if accepted:
            _urls.pop(attempt.id, None)


async def session(account_id: str | None = None) -> dict:
    """Return backend-only credential snapshot, refreshing serially when necessary."""
    async with transaction() as state:
        # An explicitly selected account (the designated sponsor) is independent
        # of the shared UI billing choice made by a local personal connection.
        mode = "chatgpt" if account_id is not None else state["mode"]
        selected_id = account_id if account_id is not None else state["active"]
        account = state["accounts"].get(selected_id)
        if mode != "chatgpt":
            return {"mode": mode, "account": None}
        if not account or not account.get("access_token"):
            return {
                "mode": mode,
                "account": account,
                "status": "reauth_required" if account else "disconnected",
            }
        now = time.time()
        if account["expires_at"] <= now + 60:
            if now < account.get("earliest_refresh_at", 0):
                if account["expires_at"] <= now:
                    return {"mode": mode, "account": account, "status": "unavailable"}
            else:
                try:
                    await discovery()
                    code, raw = await http(
                        "POST",
                        EXPECTED_ENDPOINTS["token_endpoint"],
                        {
                            "grant_type": "refresh_token",
                            "client_id": account["client_id"],
                            "refresh_token": account["refresh_token"],
                            "resource": RESOURCE,
                        },
                    )
                    if code != 200:
                        error = raw.get("error")
                        error = error.get("code") if isinstance(error, dict) else error
                        if error in TERMINAL_REFRESH:
                            for key in ("access_token", "refresh_token", "id_token"):
                                account.pop(key, None)
                            return {"mode": mode, "account": account, "status": "reauth_required"}
                        return {
                            "mode": mode,
                            "account": account,
                            "status": "unavailable",
                            "configuration_error": error == "invalid_client",
                        }
                    refreshed = await validate_tokens(
                        raw, account["client_id"], None, account, state["ext_agent_host_id"]
                    )
                    state["accounts"][selected_id] = account = refreshed
                except (
                    httpx.HTTPError,
                    TimeoutError,
                    ValueError,
                    KeyError,
                    TypeError,
                    jwt.PyJWTError,
                    AuthFailure,
                ):
                    return {"mode": mode, "account": account, "status": "unavailable"}
        status = "connected" if PLAN_SCOPES.issubset(account["scopes"]) else "plan_not_permitted"
        return {
            "mode": mode,
            "account": dict(account),
            "status": status,
            "account_id": selected_id,
        }


async def save_api_key(value: str) -> None:
    """Persist a user's explicitly supplied key in their private account store."""
    api_key = value.strip()
    if not 20 <= len(api_key) <= 1024 or any(character.isspace() for character in api_key):
        raise ProjectError("Enter a valid API key.")
    async with transaction() as state:
        state["api_key"] = api_key
        state["mode"] = "api_key"


async def api_key_token() -> str | None:
    """Return the server-only saved API key to the provider adapter."""
    async with transaction() as state:
        value = state.get("api_key")
        return value if isinstance(value, str) and value else None


async def preferences() -> dict:
    async with transaction() as state:
        return {
            "mode": state["mode"],
            "active_account": state["active"],
            "accounts": [
                {
                    "id": key,
                    "label": (account.get("email") or account.get("name") or "ChatGPT account")
                    + " · "
                    + account["client_id"][-6:],
                }
                for key, account in state["accounts"].items()
            ],
            "welcome_pending": not state["welcome_seen"],
            "usage_url": USAGE_URL,
        }


async def select(mode: str, account_id: str | None = None) -> None:
    if mode not in {"chatgpt", "api_key"}:
        raise ProjectError("Choose ChatGPT plan or API-key billing explicitly.")
    async with transaction() as state:
        if account_id is not None:
            if account_id not in state["accounts"]:
                raise ProjectError("Account was not found.")
            state["active"] = account_id
        state["mode"] = mode


async def welcome_seen() -> None:
    async with transaction() as state:
        state["welcome_seen"] = True


async def disconnect() -> dict:
    for attempt in list(_attempts.values()):
        cancel(attempt.id)
    confirmed = False
    async with transaction() as state:
        had_api_key = bool(state.pop("api_key", None))
        account = state["accounts"].get(state["active"])
        if account and account.get("refresh_token"):
            try:
                endpoints = await discovery()
                for delay in (0, 0.2):
                    if delay:
                        await asyncio.sleep(delay)
                    code, _ = await http(
                        "POST",
                        endpoints["revocation_endpoint"],
                        {
                            "token": account["refresh_token"],
                            "token_type_hint": "refresh_token",
                            "client_id": account["client_id"],
                        },
                    )
                    if code == 200:
                        confirmed = True
                        break
                    if code < 500:
                        break
            except (httpx.HTTPError, TimeoutError, ValueError, AuthFailure):
                pass
        if account:
            for key in ("access_token", "refresh_token", "id_token"):
                account.pop(key, None)
    return {
        "remote_revocation_confirmed": confirmed,
        "message": "Saved API key removed from SIGMA."
        if had_api_key
        else "Disconnected; renewable session revoked."
        if confirmed
        else "Local tokens cleared. Remote revocation was not confirmed; disconnect SIGMA in ChatGPT Settings → Usage if needed.",
    }


async def hosted_callback(identifier: str, query: str) -> None:
    """Forward a public HTTPS OAuth callback to the existing single-use verifier."""
    attempt = _attempts.get(identifier)
    if not attempt or not attempt.hosted or attempt.status != "connecting":
        raise ProjectError("ChatGPT sign-in attempt is not active.")
    # Only the validated HTTPS route can reach this bridge. The verifier checks
    # the exact Host, callback path, OAuth state, nonce and PKCE code exchange.
    target = "/api/ai/auth/callback/" + identifier
    if query:
        target += "?" + query
    host = urlsplit(attempt.redirect_uri).netloc
    if attempt.server is None:
        raise ProjectError("Sign-in callback listener is unavailable.")
    reader, writer = await asyncio.open_connection(
        "127.0.0.1", attempt.server.sockets[0].getsockname()[1]
    )
    try:
        writer.write(f"GET {target} HTTP/1.1\r\nHost: {host}\r\n\r\n".encode("ascii"))
        await writer.drain()
        await asyncio.wait_for(reader.read(4096), timeout=25)
    finally:
        writer.close()
        await writer.wait_closed()
