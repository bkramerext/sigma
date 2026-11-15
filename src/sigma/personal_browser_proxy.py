"""Per-Google-user HTTPS view of the isolated, localhost-based browser.

Never publish noVNC directly. Static noVNC assets and binary RFB frames are
forwarded only after SIGMA validates the current Google session. The remote
worker name is derived from the server's private workspace mapping, not input.
All OpenAI OAuth and inference requests remain disabled in this synthetic POC.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import secrets

import httpx
from fastapi import HTTPException, Request, WebSocket
from fastapi.responses import HTMLResponse, Response

from sigma import cloud_auth, personal_browser

_ASSET = re.compile(r"[a-zA-Z0-9_./-]{1,240}\Z")
_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_WINDOW_ID = re.compile(r"[0-9a-f]{32}\Z")


def valid_window(request: Request | WebSocket, window_id: str) -> bool:
    """Reject malformed or foreign window paths before resolving sessions."""
    if window_id != "unscoped" and not _WINDOW_ID.fullmatch(window_id):
        return False
    selected = cloud_auth._window_id(request)  # type: ignore[arg-type]
    return selected is None if window_id == "unscoped" else selected == window_id


def _principal(request: Request) -> cloud_auth.Principal:
    principal = getattr(request.state, "cloud_principal", None)
    if (
        not isinstance(principal, cloud_auth.Principal)
        or principal.role not in {"admin", "member"}
        or principal.subject.startswith("mock:")
    ):
        raise HTTPException(403, "Authenticated SIGMA member required.")
    return principal


async def _ready(principal: cloud_auth.Principal) -> str:
    try:
        state = await personal_browser.session(principal)
        if state["browser_status"] != "ready":
            raise personal_browser.PersonalBrowserUnavailable("Browser is not running")
        return await personal_browser.browser_socket(principal)
    except personal_browser.PersonalBrowserUnavailable as exc:
        raise HTTPException(503, "Private browser is unavailable.") from exc


async def view(request: Request) -> HTMLResponse:
    """One authenticated page; includes only a per-session VNC control secret."""
    principal = _principal(request)
    await _ready(principal)
    try:
        password = await personal_browser.browser_password(principal)
    except personal_browser.PersonalBrowserUnavailable as exc:
        raise HTTPException(503, "Private browser is unavailable.") from exc

    window_id = cloud_auth._window_id(request)
    prefix = "/api/ai/personal-browser/window/" + (window_id or "unscoped")
    nonce = secrets.token_urlsafe(20)
    script = """
const status = document.querySelector('#connection-status');
const cancel = document.querySelector('#cancel-connection');
cancel.addEventListener('click', () => {
  void fetch(__STOP_URL__, {method: 'POST', keepalive: true}).catch(() => {});
  window.close();
});
const previewUrl = __PREVIEW_URL__;
const messages = {
  ready: 'Ready to sign in. Click Continue with ChatGPT in the browser below.',
  connecting: 'Waiting for ChatGPT sign-in to finish.',
  connected: 'ChatGPT authorization verified. Finishing the connection in SIGMA…',
  plan_not_permitted: 'Signed in. ChatGPT plan permission was not granted.',
  declined: 'ChatGPT authorization was declined.',
  cancelled: 'Sign-in ended before authorization completed. Start a new sign-in to retry.',
  expired: 'Sign-in expired. Start a new sign-in to retry.',
  failed: 'ChatGPT authorization failed. Start a new sign-in to retry.',
};
let displayConnected = false;
async function watchPreview() {
  const started = Date.now();
  while (displayConnected) {
    let phase = 'unavailable';
    try {
      const response = await fetch(previewUrl, {cache: 'no-store', signal: AbortSignal.timeout(4000)});
      if (response.ok) phase = (await response.json()).phase;
    } catch {}
    if (!displayConnected) return;
    if (phase === 'rendering' || phase === 'unavailable') {
      status.textContent = Date.now() - started < 15000
        ? 'Waiting for the sign-in page to render…'
        : 'Could not confirm that the sign-in page loaded. Close this window and reopen sign-in.';
    } else if (Object.hasOwn(messages, phase)) {
      status.textContent = messages[phase];
    }
    await new Promise(resolve => setTimeout(resolve, 1200));
  }
}
try {
  const {default: RFB} = await import('__BASE__/core/rfb.js');
  const target = document.querySelector('#screen');
  const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const rfb = new RFB(
    target,
    scheme + '//' + location.host + '__BASE__/ws',
    {credentials: {password: __PASSWORD__}}
  );
  rfb.scaleViewport = true;
  rfb.resizeSession = true;
  rfb.addEventListener('connect', () => {
    cancel.hidden = true;
    displayConnected = true;
    if (previewUrl) void watchPreview();
    else status.textContent = 'Browser ready';
  });
  rfb.addEventListener('disconnect', () => {
    displayConnected = false;
    cancel.hidden = true;
    status.textContent = 'Browser disconnected. Close this window and reconnect from SIGMA.';
  });
} catch {
  cancel.hidden = true;
  status.textContent = 'Could not load the private browser. Close this window and reconnect from SIGMA.';
}
"""
    stop_url = "/api/ai/personal-browser/stop"
    preview_url = "/api/ai/personal-browser/preview-state"
    if window_id:
        suffix = "?sigma_window=" + window_id
        stop_url += suffix
        preview_url += suffix
    script = (
        script.replace("__BASE__", prefix)
        .replace("__PASSWORD__", json.dumps(password))
        .replace("__STOP_URL__", json.dumps(stop_url))
        .replace(
            "__PREVIEW_URL__",
            json.dumps(preview_url if personal_browser.sign_in_preview_enabled() else None),
        )
    )
    html = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Connect ChatGPT · SIGMA</title>"
        f"<style nonce='{nonce}'>"
        "html,body{margin:0;background:#171b20;color:white;font:14px system-ui;height:100%}"
        "main{display:flex;flex-direction:column;height:100%;overflow:hidden}"
        "header{padding:8px 16px;background:#20252b;display:flex;gap:16px}"
        "#screen{flex:1;min-height:0;overflow:hidden}#screen canvas{outline:none}"
        "</style></head><body><main>"
        "<header><strong>Connect ChatGPT</strong><span id='connection-status'>"
        "Connecting to the ChatGPT sign-in browser…</span>"
        "<button id='cancel-connection' type='button'>Cancel</button></header>"
        "<div id='screen'></div></main>"
        f"<script type='module' nonce='{nonce}'>{script}</script></body></html>"
    )
    connect = " 'self' ws: wss:"
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": (
                "default-src 'none'; "
                f"script-src 'self' 'nonce-{nonce}'; "
                f"style-src 'nonce-{nonce}'; connect-src{connect}; "
                "img-src 'self' data:; font-src 'self'; frame-ancestors 'self'"
            ),
        },
    )


async def asset(request: Request, path: str) -> Response:
    """Forward only necessary static noVNC code; never proxy OAuth/API routes."""
    principal = _principal(request)
    socket_path = await _ready(principal)
    if (
        not _ASSET.fullmatch(path)
        or ".." in path.split("/")
        or not path.startswith(("app/", "core/", "vendor/", "images/"))
    ):
        raise HTTPException(404, "Browser asset unavailable.")
    try:
        transport = httpx.AsyncHTTPTransport(uds=socket_path)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://private-browser",
            timeout=6,
            follow_redirects=False,
        ) as client:
            response = await client.get("/" + path)
        if response.status_code != 200 or len(response.content) > 2_000_000:
            raise ValueError("Invalid browser asset")
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise HTTPException(503, "Private browser asset unavailable.") from exc
    return Response(
        response.content,
        media_type=response.headers.get("content-type", "application/octet-stream"),
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


def _masked_frame(opcode: int, data: bytes) -> bytes:
    """A minimal, bounded client-to-websockify WebSocket binary frame."""
    if len(data) > 4_000_000:
        raise ValueError("Oversized RFB frame")
    head = bytearray([0x80 | opcode])
    size = len(data)
    if size < 126:
        head.append(0x80 | size)
    elif size < 65536:
        head.extend((0x80 | 126, *size.to_bytes(2, "big")))
    else:
        head.extend((0x80 | 127, *size.to_bytes(8, "big")))
    mask = os.urandom(4)
    return bytes(head) + mask + bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))


async def _remote_frame(reader: asyncio.StreamReader) -> tuple[bool, int, bytes]:
    first, second = await reader.readexactly(2)
    if first & 0x70:
        raise ValueError("Reserved WebSocket bits")
    fin = bool(first & 0x80)
    opcode = first & 15
    count = second & 127
    if count == 126:
        count = int.from_bytes(await reader.readexactly(2), "big")
    elif count == 127:
        count = int.from_bytes(await reader.readexactly(8), "big")
    if count > 4_000_000:
        raise ValueError("Oversized RFB frame")
    mask = await reader.readexactly(4) if second & 0x80 else None
    data = await reader.readexactly(count)
    if mask:
        data = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
    return fin, opcode, data


async def _connect_worker(socket_path: str) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    if not socket_path.startswith("/") or ".." in socket_path.split("/"):
        raise ValueError("Unsafe browser socket")
    reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(socket_path), timeout=5)
    key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
    writer.write(
        (
            "GET /websockify HTTP/1.1\r\n"
            "Host: private-browser\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
            "Sec-WebSocket-Protocol: binary\r\n\r\n"
        ).encode("ascii")
    )
    try:
        await asyncio.wait_for(writer.drain(), timeout=4)
        response = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5)
        if len(response) > 8192 or not response.startswith(b"HTTP/1.1 101 "):
            raise ValueError("Browser WebSocket upgrade rejected")
        headers = {}
        for line in response.decode("ascii").split("\r\n")[1:]:
            if ":" in line:
                name, value = line.split(":", 1)
                headers[name.lower()] = value.strip()
        expected = base64.b64encode(hashlib.sha1((key + _WS_GUID).encode()).digest()).decode()
        if headers.get("sec-websocket-accept") != expected:
            raise ValueError("Invalid browser WebSocket accept")
        return reader, writer
    except BaseException:
        writer.close()
        raise


async def websocket_bridge(websocket: WebSocket, window_id: str) -> None:
    """Explicit Google-session gate: HTTP auth middleware does not gate WS routes."""
    cfg = cloud_auth.config()
    if (
        not valid_window(websocket, window_id)
        or not personal_browser.enabled()
        or not cfg.enabled
        or not cfg.origin
        or websocket.headers.get("origin") != cfg.origin
    ):
        await websocket.close(code=1008)
        return
    # WebSocket has the same cookie/header/query accessors as Request. The
    # scoped session must match the initiating SIGMA browser window.
    raw = cloud_auth._raw_session(websocket, cfg)  # type: ignore[arg-type]
    principal = cloud_auth.resolve_session(raw)
    if (
        not isinstance(principal, cloud_auth.Principal)
        or principal.role not in {"admin", "member"}
        or principal.subject.startswith("mock:")
    ):
        await websocket.close(code=1008)
        return
    writer: asyncio.StreamWriter | None = None
    try:
        socket_path = await _ready(principal)
        reader, writer = await _connect_worker(socket_path)
        selected_protocol = (
            "binary"
            if "binary" in (websocket.headers.get("sec-websocket-protocol") or "").split(",")
            else None
        )
        await websocket.accept(subprotocol=selected_protocol)

        async def from_browser() -> None:
            assert writer is not None
            while True:
                item = await websocket.receive()
                if item["type"] == "websocket.disconnect":
                    break
                if item["type"] != "websocket.receive":
                    continue
                if item.get("bytes") is not None:
                    writer.write(_masked_frame(2, item["bytes"]))
                else:
                    writer.write(_masked_frame(1, (item.get("text") or "").encode()))
                await writer.drain()

        async def from_worker() -> None:
            assert writer is not None
            fragments = bytearray()
            fragment_opcode: int | None = None
            while True:
                fin, opcode, payload = await _remote_frame(reader)
                if opcode == 8:
                    break
                if opcode == 9:
                    writer.write(_masked_frame(10, payload))
                    await writer.drain()
                    continue
                if opcode == 10:
                    continue
                if opcode in (1, 2):
                    if fragment_opcode is not None:
                        raise ValueError("Overlapping WebSocket fragments")
                    fragment_opcode = opcode
                elif opcode != 0 or fragment_opcode is None:
                    raise ValueError("Invalid WebSocket continuation")
                fragments.extend(payload)
                if len(fragments) > 4_000_000:
                    raise ValueError("Oversized reassembled RFB message")
                if fin:
                    if fragment_opcode == 2:
                        await websocket.send_bytes(bytes(fragments))
                    else:
                        await websocket.send_text(fragments.decode("utf-8"))
                    fragments.clear()
                    fragment_opcode = None

        async def verify_session_continues() -> None:
            # An existing WebSocket must lose control after SIGMA logout,
            # revoked membership, or session expiry, even while a tab stays open.
            from starlette.concurrency import run_in_threadpool

            while True:
                await asyncio.sleep(5)
                current = await run_in_threadpool(cloud_auth.resolve_session, raw)
                if (
                    current is None
                    or current.subject != principal.subject
                    or current.role not in {"admin", "member"}
                ):
                    raise PermissionError("SIGMA session is no longer authorized")

        tasks = [
            asyncio.create_task(from_browser()),
            asyncio.create_task(from_worker()),
            asyncio.create_task(verify_session_continues()),
        ]
        try:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            for task in done:
                if not task.cancelled():
                    task.result()
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
    except (
        OSError,
        ValueError,
        UnicodeError,
        TimeoutError,
        asyncio.IncompleteReadError,
        asyncio.LimitOverrunError,
        HTTPException,
        PermissionError,
        personal_browser.PersonalBrowserUnavailable,
    ):
        pass
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
        try:
            await websocket.close()
        except (RuntimeError, OSError):
            pass
