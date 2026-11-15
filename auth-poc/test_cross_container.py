"""Synthetic inter-container OAuth callback test. No OpenAI traffic or credentials.

Run this command ONLY inside the credential worker. The disposable browser
container connects to the temporary loopback control port and invokes the
actual callback listener across their shared network namespace. There is no
HTTP control route in the production ASGI application.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch
from urllib.parse import urlsplit

from sigma import chatgpt_auth

CONTROL_PORT = 19091


async def main() -> None:
    with patch.object(
        chatgpt_auth,
        "discovery",
        new=AsyncMock(return_value=dict(chatgpt_auth.EXPECTED_ENDPOINTS)),
    ):
        attempt = await chatgpt_auth.begin()
    identifier = attempt["id"]
    try:
        url = chatgpt_auth.authorization_url(identifier)
        # Only return an invalid-state callback URL, never auth code, verifier,
        # real state or any credential.
        from urllib.parse import parse_qs

        callback = parse_qs(urlsplit(url).query)["redirect_uri"][0]
        target = callback + "?code=invalid&state=invalid"
        completed = asyncio.Event()
        observed_callback = asyncio.Event()
        original_callback = chatgpt_auth.callback

        async def observe_callback(*args, **kwargs) -> None:
            try:
                await original_callback(*args, **kwargs)
            finally:
                observed_callback.set()

        async def handle(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            try:
                request = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 4)
                first = request.split(b"\r\n", 1)[0]
                if first == b"GET /target HTTP/1.1":
                    body = target.encode("ascii")
                    status = b"200 OK"
                elif first == b"GET /done HTTP/1.1":
                    if not observed_callback.is_set():
                        status, body = b"425 Too Early", b"WAIT"
                    else:
                        safe = chatgpt_auth.attempt_status(identifier)["status"] == "connecting"
                        status = b"200 OK" if safe else b"409 Conflict"
                        body = b"PASS" if safe else b"FAIL"
                        completed.set()
                else:
                    status, body = b"404 Not Found", b""
                writer.write(
                    b"HTTP/1.1 "
                    + status
                    + b"\r\nContent-Type: text/plain\r\nCache-Control: no-store\r\n"
                    + b"Connection: close\r\nContent-Length: "
                    + str(len(body)).encode()
                    + b"\r\n\r\n"
                    + body
                )
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        # Observe the existing OAuth listener itself; do not confuse a
        # Chromium process exiting with an actual callback being received.
        with patch.object(chatgpt_auth, "callback", new=observe_callback):
            async with await asyncio.start_server(handle, "127.0.0.1", CONTROL_PORT):
                await asyncio.wait_for(completed.wait(), timeout=45)
        assert observed_callback.is_set(), "Chromium did not reach the callback"
        assert chatgpt_auth.attempt_status(identifier)["status"] == "connecting"
        print("PASS: browser container reached worker callback over shared localhost", flush=True)
    finally:
        chatgpt_auth.cancel(identifier)


if __name__ == "__main__":
    asyncio.run(main())
