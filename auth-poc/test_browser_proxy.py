"""Credential-free end-to-end checks of SIGMA's per-user browser HTTPS proxy."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException, Request, WebSocket

from sigma import api, cloud_auth, personal_browser_proxy as proxy

A = cloud_auth.Principal("subject-a", "a@example.test", "member")
B = cloud_auth.Principal("subject-b", "b@example.test", "member")


def request(principal: cloud_auth.Principal, path: str = "/") -> Request:
    value = Request(
        {"type": "http", "method": "GET", "path": path, "headers": [], "query_string": b""}
    )
    value.state.cloud_principal = principal
    return value


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sigma-browser-relay-") as directory:
        sockets = {A.subject: str(Path(directory) / "a.sock"),
                   B.subject: str(Path(directory) / "b.sock")}
        servers = []

        async def start(subject: str) -> None:
            async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
                try:
                    req = await reader.readuntil(b"\r\n\r\n")
                    if req.startswith(b"GET /websockify HTTP/1.1"):
                        key = next(
                            line.split(b": ", 1)[1].strip()
                            for line in req.split(b"\r\n")
                            if line.lower().startswith(b"sec-websocket-key:")
                        )
                        accept = base64.b64encode(
                            hashlib.sha1(key + proxy._WS_GUID.encode()).digest()
                        )
                        writer.write(
                            b"HTTP/1.1 101 Switching Protocols\r\n"
                            b"Upgrade: websocket\r\nConnection: Upgrade\r\n"
                            b"Sec-WebSocket-Accept: " + accept + b"\r\n\r\n"
                            b"\x82\x03yes"
                        )
                    else:
                        assert req.startswith(b"GET /core/rfb.js HTTP/1.1")
                        body = ("// only " + subject).encode()
                        writer.write(
                            b"HTTP/1.1 200 OK\r\nContent-Type: text/javascript\r\n"
                            + b"Content-Length: " + str(len(body)).encode()
                            + b"\r\nConnection: close\r\n\r\n" + body
                        )
                    await writer.drain()
                finally:
                    writer.close()
                    await writer.wait_closed()

            servers.append(await asyncio.start_unix_server(handler, sockets[subject]))

        await start(A.subject)
        await start(B.subject)
        try:
            def identity(principal: cloud_auth.Principal) -> str:
                return sockets[principal.subject]

            async def browser_socket(principal: cloud_auth.Principal) -> str:
                return identity(principal)

            async def browser_password(principal: cloud_auth.Principal) -> str:
                return "AB12CD34" if principal.subject == A.subject else "EF56GH78"

            with (
                patch.object(
                    proxy.personal_browser, "session",
                    new=AsyncMock(return_value={"browser_status": "ready"}),
                ),
                patch.object(proxy.personal_browser, "browser_socket", new=browser_socket),
                patch.object(proxy.personal_browser, "browser_password", new=browser_password),
                patch.object(proxy.cloud_auth, "config", return_value=SimpleNamespace(enabled=True, local=False, origin="https://sigma.example.test")),
            ):
                a = await proxy.asset(request(A), "core/rfb.js")
                b = await proxy.asset(request(B), "core/rfb.js")
                assert a.body == b"// only subject-a"
                assert b.body == b"// only subject-b"
                assert a.headers["cache-control"] == "no-store"
                # Test actual window-scoped route registration and dispatch,
                # not just the underlying asset or WebSocket proxy functions.
                routes = {(route.path, type(route).__name__) for route in api.app.routes if hasattr(route, "path")}
                assert (
                    "/api/ai/personal-browser/window/{window_id}/{path:path}",
                    "APIRoute",
                ) in routes
                assert (
                    "/api/ai/personal-browser/window/{window_id}/ws",
                    "APIWebSocketRoute",
                ) in routes
                window_id = "a" * 32
                qualified = "/api/ai/personal-browser/window/" + window_id + "/core/rfb.js"
                assert proxy.valid_window(request(A, qualified), window_id)
                routed = await api.personal_browser_asset(
                    request(A, qualified), window_id=window_id, path="core/rfb.js"
                )
                assert routed.body == b"// only subject-a"
                assert not proxy.valid_window(request(A, qualified), "b" * 32)
                try:
                    await api.personal_browser_asset(
                        request(A, qualified), window_id="invalid", path="core/rfb.js"
                    )
                except HTTPException as error:
                    assert error.status_code == 404
                else:
                    raise AssertionError("Invalid browser window route accepted")
                html_a = await proxy.view(request(A))
                html_b = await proxy.view(request(B))
                assert "AB12CD34" in html_a.body.decode()
                assert "EF56GH78" not in html_a.body.decode()
                assert "EF56GH78" in html_b.body.decode()
                assert html_a.headers["cache-control"] == "no-store"
                for bad in ("../../private", "app/../../private", "http://another-host"):
                    try:
                        await proxy.asset(request(A), bad)
                    except HTTPException as error:
                        assert error.status_code == 404
                    else:
                        raise AssertionError("Unsafe asset path was proxied")
                reader, writer = await proxy._connect_worker(sockets[A.subject])
                try:
                    fin, opcode, payload = await proxy._remote_frame(reader)
                    assert fin and opcode == 2 and payload == b"yes"
                finally:
                    writer.close()
                    await writer.wait_closed()
                try:
                    await proxy.view(request(cloud_auth.Principal("guest", "g@test", "guest")))
                except HTTPException as error:
                    assert error.status_code == 403
                else:
                    raise AssertionError("Guest received private browser")
                # WebSockets do not traverse SIGMA's HTTP Google auth middleware.
                # Verify both the immutable window selector and Origin are
                # rejected before any worker channel is opened.
                async def denied_ws(path: str, identifier: str, origin: str) -> None:
                    sent: list[dict[str, object]] = []

                    async def receive() -> dict[str, str]:
                        return {"type": "websocket.connect"}

                    async def send(message: dict[str, object]) -> None:
                        sent.append(message)

                    ws = WebSocket(
                        {
                            "type": "websocket",
                            "scheme": "wss",
                            "path": path,
                            "query_string": b"",
                            "headers": [(b"origin", origin.encode("ascii"))],
                        },
                        receive,
                        send,
                    )
                    with patch.object(proxy.personal_browser, "enabled", return_value=True):
                        await proxy.websocket_bridge(ws, identifier)
                    assert sent and sent[0]["type"] == "websocket.close"
                    assert sent[0]["code"] == 1008

                ws_path = "/api/ai/personal-browser/window/" + window_id + "/ws"
                await denied_ws(ws_path, "invalid", "https://sigma.example.test")
                await denied_ws(ws_path, "b" * 32, "https://sigma.example.test")
                await denied_ws(ws_path, window_id, "https://attacker.example.test")
                with patch.object(proxy.cloud_auth, "resolve_session", return_value=None):
                    await denied_ws(ws_path, window_id, "https://sigma.example.test")
        finally:
            for server in servers:
                server.close()
                await server.wait_closed()
    print("PASS private browser UDS assets, WebSocket framing, user identity and denial")


if __name__ == "__main__":
    asyncio.run(main())
