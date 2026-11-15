"""Container-local OAuth callback boundary test without provider credentials."""
from __future__ import annotations
import asyncio
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit
from sigma import chatgpt_auth

async def exercise() -> None:
    with patch.object(chatgpt_auth, "discovery", new=AsyncMock(return_value=dict(chatgpt_auth.EXPECTED_ENDPOINTS))):
        attempt = await chatgpt_auth.begin()
    identifier = attempt["id"]
    try:
        authorization = chatgpt_auth.authorization_url(identifier)
        params = parse_qs(urlsplit(authorization).query)
        target = urlsplit(params["redirect_uri"][0])
        assert target.scheme == "http"
        assert target.hostname == "127.0.0.1"
        assert target.path == "/auth/callback"
        assert target.port and 0 < target.port < 65536
        assert params["code_challenge_method"] == ["S256"]
        reader, writer = await asyncio.open_connection("127.0.0.1", target.port)
        writer.write(b"GET /auth/callback?code=invalid&state=invalid HTTP/1.1\r\n"
                     + ("Host: 127.0.0.1:" + str(target.port)).encode("ascii")
                     + b"\r\nConnection: close\r\n\r\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), timeout=5)
        # The callback deliberately returns a neutral HTTP 200 even for an
        # invalid OAuth state; the attempt must stay unconsumed and unconnected.
        assert response.startswith(b"HTTP/1.1 200 OK\r\n"), response[:80]
        assert b"Return to SIGMA" in response
        assert b"invalid" not in response.lower()
        writer.close()
        await writer.wait_closed()
        assert chatgpt_auth.attempt_status(identifier)["status"] == "connecting"
    finally:
        chatgpt_auth.cancel(identifier)

if __name__ == "__main__":
    asyncio.run(exercise())
    print("PASS container localhost listener, PKCE and invalid-state rejection")
