"""Real loopback + signed OIDC + bounded SSE fixtures; no live account or inference."""

import asyncio
import copy
import json
import os
import stat
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

import httpx
from siwc_fixture import DRAFT, Fixture

from sigma import chatgpt_auth as auth
from sigma import openai_connection as connection
from sigma.ai_store import directory, transaction
from sigma.api import app
from sigma.investigations import InvestigationError, initialize_investigation, inspect_investigation
from sigma.proposals import accepted_provenance, configuration, generate_proposal

REAL_CLIENT = httpx.AsyncClient


async def rejection(awaitable, text=None):
    try:
        await awaitable
    except InvestigationError as error:
        if text:
            assert text in str(error), str(error)
    else:
        raise AssertionError("Expected rejection")


async def callback(url, headers=None):
    async with REAL_CLIENT(timeout=15, trust_env=False) as client:
        try:
            return await client.get(url, headers=headers)
        except httpx.ConnectError:
            return None  # Already consumed single-use listener.


async def sign_in(fixture, account_id=None, error=None, override=None):
    started = await auth.begin(account_id)
    url = fixture.authorize(
        auth.authorization_url(started["id"]), error=error, client_override=override
    )
    await callback(url)
    return started, auth.attempt_status(started["id"])


def reset_connection():
    connection._cached, connection._identity, connection._known = None, "", set()
    connection._pending = None


async def checks(root):
    fixture = Fixture()

    def client(**kwargs):
        return REAL_CLIENT(transport=httpx.MockTransport(fixture.handler), **kwargs)

    async with REAL_CLIENT(
        transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000"
    ) as api:
        for origin in (None, "https://foreign.example", "null"):
            response = await api.post(
                "/api/ai/mode",
                json={"mode": "api_key"},
                headers={"Origin": origin} if origin else {},
            )
            assert response.status_code == 403
        response = await api.post(
            "/api/ai/mode",
            content='{"mode":"api_key"}',
            headers={"Origin": "http://127.0.0.1:5173", "Content-Type": "text/plain"},
        )
        assert response.status_code == 403
    with patch("httpx.AsyncClient", side_effect=client):
        # A saved key never selects API billing or triggers any provider request.
        state = await connection.connection()
        assert (
            state["status"] == "disconnected"
            and state["label"] == "Connect AI"
            and not fixture.requests
        )
        before_prefs = await auth.preferences()
        started, result = await sign_in(fixture)
        assert result["status"] == "connected"
        state = await connection.connection()
        assert (
            state["mode"] == "chatgpt"
            and state["status"] == "connected"
            and state["welcome_pending"]
        )
        assert state["account_label"] == "same-email@example.test"
        assert fixture.generated == 0
        serialized = json.dumps(state)
        assert all(token not in serialized for token in fixture.tokens)
        assert directory().stat().st_mode & 0o777 == 0o700
        assert (directory() / "credentials.json").stat().st_mode & 0o777 == 0o600
        async with transaction() as stored:
            host = stored["ext_agent_host_id"]
            first_id = stored["active"]
            first_record = copy.deepcopy(stored["accounts"][first_id])
        await auth.welcome_seen()
        assert not (await connection.connection())["welcome_pending"]
        # Returning sign-in uses issued ID and validated hints; no new registration.
        _, result = await sign_in(fixture, first_id)
        assert result["status"] == "connected"
        async with transaction() as stored:
            assert stored["ext_agent_host_id"] == host
            assert stored["accounts"][first_id]["client_id"] == first_record["client_id"]
            stored["accounts"][first_id]["expires_at"] = time.time() - 1
            stored["accounts"][first_id]["earliest_refresh_at"] = time.time() - 1
        # Concurrent callers and a fresh module/client read the rotated record once.
        contexts = await asyncio.gather(*(auth.session() for _ in range(8)))
        assert fixture.refreshed == 1 and all(
            context["status"] == "connected" for context in contexts
        )
        async with transaction() as stored:
            assert stored["accounts"][first_id]["refresh_token"] != first_record["refresh_token"]
            assert stored["ext_agent_host_id"] == host
            stored["accounts"][first_id]["expires_at"] = time.time() - 1
            stored["accounts"][first_id]["earliest_refresh_at"] = time.time() + 60
        assert (await auth.session())["status"] == "unavailable" and fixture.refreshed == 1
        async with transaction() as stored:
            stored["accounts"][first_id]["expires_at"] = time.time() + 3600
        print(
            "PASS public OSS registration/PKCE, exact real loopback exchange, signed OIDC, safe payloads, stable host, retained issued ID, welcome once, serial rotating refresh and earliest-refresh boundary"
        )

        fixture.code_error = "invalid_grant"
        started, result = await sign_in(fixture)
        assert result["status"] == "failed" and result["retryable"]
        fixture.code_error = None
        retried = await auth.begin(retry_attempt_id=started["id"])
        retry_url = auth.authorization_url(retried["id"])
        assert parse_qs(urlsplit(retry_url).query)["client_id"][0] != "dynamic_agent_client"
        await callback(fixture.authorize(retry_url))
        assert auth.attempt_status(retried["id"])["status"] == "connected"
        await auth.select("chatgpt", first_id)
        async with transaction() as stored:
            # This verified test registration is independent; keep later account-count assertion scoped.
            extra = next(key for key in stored["accounts"] if key != first_id)
            stored["accounts"].pop(extra)
        # Failed callbacks/identities never replace the active usable account.
        for claim in (
            {"nonce": "wrong"},
            {"iss": "https://untrusted.example"},
            {"aud": "different-client"},
            {"exp": int(time.time()) - 5},
            {"sub": "mismatched-returning-account"},
        ):
            fixture.claims_override = claim
            _, result = await sign_in(fixture, first_id)
            assert result["status"] == "failed"
            assert (await auth.session())["account"]["subject"] == first_record["subject"]
        fixture.claims_override = {}
        for field in ("access_token", "refresh_token", "id_token", "token_type", "scope"):
            fixture.token_override = {field: ""}
            _, result = await sign_in(fixture, first_id)
            assert result["status"] == "failed"
        fixture.token_override = {}
        original_key = fixture.key
        fixture.key = Fixture().key
        _, result = await sign_in(fixture, first_id)
        assert result["status"] == "failed"
        fixture.key = original_key
        started = await auth.begin(first_id)
        url = fixture.authorize(auth.authorization_url(started["id"]))
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        query["state"] = ["wrong-state"]
        bad_url = urlunsplit(
            parsed._replace(query=urlencode({key: values[0] for key, values in query.items()}))
        )
        await callback(bad_url)
        assert auth.attempt_status(started["id"])["status"] == "connecting"
        await callback(url, {"Origin": "https://foreign.example"})
        assert auth.attempt_status(started["id"])["status"] == "connecting"
        before_count = len(fixture.tokens)
        await asyncio.gather(callback(url), callback(url))
        assert (
            len(fixture.tokens) == before_count + 3
            and auth.attempt_status(started["id"])["status"] == "connected"
        )
        _, result = await sign_in(fixture, first_id, override="oaiapp_wrong-client")
        assert result["status"] == "failed"
        _, result = await sign_in(fixture, first_id, error="access_denied")
        assert result["status"] == "declined"
        started = await auth.begin()
        auth.cancel(started["id"])
        assert auth.attempt_status(started["id"])["status"] == "cancelled"
        assert (await auth.preferences())["active_account"] == first_id
        fixture.discovery_override = {"token_endpoint": "https://foreign.example/token"}
        await rejection(auth.begin(), "discovery")
        fixture.discovery_override = {}
        print(
            "PASS invalid state/origin/nonce/signature/issuer/audience/expiry/subject/client, missing tokens, declined/cancelled sign-in, duplicate callback race and endpoint mixup never replace credentials"
        )

        fixture.subject = "fixture-subject-two"
        fixture.scope = "openid profile email offline_access resource.invoke"
        _, result = await sign_in(fixture)
        assert result["status"] == "plan_not_permitted"
        denied_id = (await auth.preferences())["active_account"]
        assert denied_id != first_id and len((await auth.preferences())["accounts"]) == 2
        assert (await connection.connection())["status"] == "plan_not_permitted"
        fixture.scope = auth.SCOPES
        _, result = await sign_in(fixture, denied_id)
        assert result["status"] == "connected"
        await auth.select("chatgpt", first_id)
        assert (await auth.session())["account"]["subject"] == first_record["subject"]
        reset_connection()
        plan_catalog = await connection.models()
        assert plan_catalog["default_verified"]
        fixture.catalog_override = {"object": "list", "data": [{"id": "gpt-6.1-sol"}]}
        reset_connection()
        assert (await connection.connection())["status"] == "invalid_response"
        fixture.catalog_override = None
        reset_connection()
        path = root / "plan.sigma"
        initialize_investigation(
            path, "Plan fixture", "A bounded mathematical question", "mathematical"
        )
        before = (path / "investigation.json").read_bytes()
        config = await configuration(str(path))
        generated = await generate_proposal(
            str(path),
            "Keep this seed",
            expected_binding=config["binding"],
            expected_investigation_id=config["investigation_id"],
        )
        assert generated["draft"] == DRAFT
        assert (
            accepted_provenance(generated["receipt"], str(path)).model
            == "gpt-6.1-sol-fixture-returned"
        )
        assert (
            inspect_investigation(path).investigation.reasoning_effort == "high"
            and (path / "investigation.json").read_bytes() == before
        )
        assert fixture.generated == 1
        await rejection(
            generate_proposal(str(path), expected_investigation_id="changed"), "identity"
        )
        await rejection(generate_proposal(str(path), expected_binding="api_key"), "billing mode")
        # SSE malformed/failed/incomplete/refusal/truncated/oversized/out-of-order streams.
        events = fixture.events()
        cases = [b"data: not-json\n\n", b"data: [DONE]\n\n", b"x" * 1000001]
        for index in (0, 1, 2):
            altered = copy.deepcopy(events)
            if index == 0:
                altered[1]["sequence_number"] = 0
            elif index == 1:
                altered[-1]["response"]["id"] = "wrong-response"
            else:
                altered = altered[:-1]
            cases.append(
                "".join("data: " + json.dumps(event) + "\n\n" for event in altered).encode()
            )
        for kind in ("response.failed", "response.incomplete"):
            altered = [
                events[0],
                {
                    "type": kind,
                    "sequence_number": 1,
                    "response": {
                        "id": "resp-fixture",
                        "status": kind.split(".")[1],
                        "error": {"code": "subscription_sharing_usage_limit_exceeded"},
                    },
                },
            ]
            cases.append(
                "".join("data: " + json.dumps(event) + "\n\n" for event in altered).encode()
            )
        for content in cases:
            fixture.stream_override = content
            reset_connection()
            await rejection(generate_proposal(str(path)))
            assert (path / "investigation.json").read_bytes() == before
        fixture.stream_override = None
        for status, code, expected in (
            (429, "subscription_sharing_usage_limit_exceeded", "limited"),
            (403, "subscription_sharing_user_not_eligible", "forbidden"),
            (400, "subscription_sharing_unsupported_capability", "forbidden"),
            (401, "subscription_sharing_invalid_user", "unauthorized"),
            (503, "subscription_sharing_usage_unavailable", "unavailable"),
        ):
            fixture.inference_error = (
                status,
                {"error": {"code": code, "message": "never reflect raw provider body"}},
            )
            reset_connection()
            await rejection(generate_proposal(str(path)))
            assert (await connection.connection())["status"] == expected
            assert (await auth.preferences())["mode"] == "chatgpt"
        fixture.inference_error = None
        # Both catalog shapes are distinct; a key needs explicit mode, not a flag.
        await auth.select("api_key")
        reset_connection()
        assert (await connection.connection())["status"] == "connected"
        assert (await configuration(str(path)))["mode"] == "api_key"
        key_draft = await generate_proposal(str(path))
        assert key_draft["draft"] == DRAFT and "SIGMA_AI_ENABLED" not in os.environ
        await auth.select("chatgpt", first_id)
        async with transaction() as stored:
            stored["accounts"][first_id]["expires_at"] = time.time() - 1
            stored["accounts"][first_id]["earliest_refresh_at"] = time.time() - 1
        fixture.refresh_error = "refresh_token_reused"
        assert (await auth.session())["status"] == "reauth_required"
        async with transaction() as stored:
            assert "refresh_token" not in stored["accounts"][first_id]
        assert (await auth.preferences())["mode"] == "chatgpt"
        fixture.refresh_error = None
        fixture.subject = first_record["subject"]
        await sign_in(fixture, first_id)
        fixture.revocation_error = True
        assert not (await auth.disconnect())["remote_revocation_confirmed"]
        assert (await auth.session())["status"] == "reauth_required"
        await sign_in(fixture, first_id)
        fixture.revocation_error = False
        assert (await auth.disconnect())["remote_revocation_confirmed"]
        assert (await auth.preferences())["mode"] == "chatgpt"
        assert before_prefs["mode"] == "chatgpt"
        state_path = directory() / "credentials.json"
        assert stat.S_IMODE(state_path.stat().st_mode) == 0o600
        saved = state_path.read_bytes()
        state_path.chmod(0o644)
        await rejection(auth.preferences(), "storage")
        offline = await connection.models()
        assert (
            offline["connection"]["mode"] == "unknown" and offline["default_model"] == "gpt-6.1-sol"
        )
        assert offline["models"] and not offline["default_verified"]
        state_path.chmod(0o600)
        assert state_path.read_bytes() == saved
        print(
            "PASS scope decline/enable, multi-account isolation, mode-specific catalogs, strict streamed Responses completion/failures/limits, no generation/save on sign-in, no billing fallback, investigation/account intent binding, key mode without flag, terminal refresh and confirmed/unconfirmed revoke"
        )


def main():
    with (
        TemporaryDirectory() as temporary,
        patch.dict(
            os.environ,
            {
                "SIGMA_AUTH_HOME": str(Path(temporary) / "accounts"),
                "OPENAI_API_KEY": "explicit-api-key-fixture",
            },
        ),
    ):
        os.environ.pop("SIGMA_AI_ENABLED", None)
        asyncio.run(checks(Path(temporary)))


if __name__ == "__main__":
    main()
