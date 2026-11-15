"""Admin-gated synthetic browser preview served only behind trusted Caddy.

This app has no production authentication store, inference route, or public
listener. Caddy validates the real SIGMA admin session before proxying each
HTTP request and WebSocket upgrade, then adds a short-lived edge-only key and
strips browser credentials. The preview uses one server-created workspace.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import os
import secrets

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import HTMLResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from sigma import cloud_auth, personal_browser, personal_browser_proxy

PREFIX = "/__personal_lab__"
REAL_SIGNIN = os.environ.get("SIGMA_AUTH_POC_REAL_SIGNIN", "0")
if REAL_SIGNIN != "0":
    raise RuntimeError("Synthetic preview requires real ChatGPT sign-in to be disabled")
if os.environ.get("SIGMA_AUTH_POC_PREVIEW_ENABLED") != "1":
    raise RuntimeError("Synthetic preview is not enabled")

_HOST = os.environ.get("SIGMA_PERSONAL_LAB_HOST", "").strip().lower()
_EDGE_KEY = os.environ.get("SIGMA_PERSONAL_LAB_EDGE_KEY", "")
_SUBJECT = os.environ.get("SIGMA_PERSONAL_LAB_SUBJECT", "").strip()
_EMAIL = os.environ.get("SIGMA_PERSONAL_LAB_ADMIN_EMAIL", "").strip().lower()
if not _HOST or "/" in _HOST or ":" in _HOST or not _EDGE_KEY or len(_EDGE_KEY) < 32:
    raise RuntimeError("Synthetic preview host or private edge key is invalid")
if not _SUBJECT or len(_SUBJECT) > 128 or not _EMAIL:
    raise RuntimeError("Synthetic preview principal is not configured")

_ORIGIN = "https://" + _HOST
_PRINCIPAL = cloud_auth.Principal(_SUBJECT, _EMAIL, "admin")
_MAX_WS_SECONDS = 60


class TrustedEdgeOnly:
    """Require Caddy's private proof and refuse leaked browser credentials."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        host = headers.get(b"host", b"").decode("latin-1").split(":", 1)[0].lower()
        supplied = headers.get(b"x-sigma-personal-lab-edge", b"").decode("latin-1")
        credentials = b"cookie" in headers or b"authorization" in headers
        if host != _HOST or not hmac.compare_digest(supplied, _EDGE_KEY) or credentials:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            else:
                body = b"Preview unavailable."
                await send(
                    {
                        "type": "http.response.start",
                        "status": 403,
                        "headers": [
                            (b"content-type", b"text/plain; charset=utf-8"),
                            (b"cache-control", b"no-store"),
                            (b"content-length", str(len(body)).encode("ascii")),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
            return
        state = scope.setdefault("state", {})
        state["cloud_principal"] = _PRINCIPAL
        await self.app(scope, receive, send)


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=[_HOST])
app.add_middleware(TrustedEdgeOnly)


def _origin_allowed(request: Request) -> None:
    if request.headers.get("origin") != _ORIGIN:
        raise HTTPException(403, "Same-origin preview request required.")


def _require_preview_path(request: Request) -> None:
    if not request.url.path.startswith(PREFIX + "/"):
        raise HTTPException(404, "Preview route unavailable.")


@app.get(PREFIX, include_in_schema=False)
async def root_redirect() -> Response:
    return Response(
        status_code=307,
        headers={"Location": PREFIX + "/", "Cache-Control": "no-store"},
    )


@app.get(PREFIX + "/", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request) -> HTMLResponse:
    _require_preview_path(request)
    principal = request.state.cloud_principal
    if principal.role != "admin":
        raise HTTPException(403, "Administrator access required.")
    # The server principal is a fixed synthetic admin identity. The actual
    # production administrator email is neither forwarded nor displayed.
    nonce = secrets.token_urlsafe(20)
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,">
<title>SIGMA · Synthetic Personal browser preview</title>
<style nonce="{nonce}">
:root{{color-scheme:dark;font:15px/1.5 system-ui,sans-serif;background:#15191e;color:#eff1f3}}
body{{margin:0}}main{{max-width:960px;margin:48px auto;padding:0 24px}}
.bar{{display:flex;align-items:center;gap:12px;border-bottom:1px solid #363c43;padding:14px 0}}
.brand{{font-size:19px;font-weight:650;margin-right:auto}}
button{{font:inherit;color:inherit;background:#252b32;border:1px solid #59616a;border-radius:8px;padding:8px 14px;cursor:pointer}}
button:hover{{background:#343c45}}button:focus-visible{{outline:2px solid #e3b783;outline-offset:2px}}
.pill{{border-radius:999px;padding:6px 14px;background:#252b32}}
.menu{{position:absolute;z-index:2;margin-top:4px;background:#20252b;border:1px solid #49515a;border-radius:10px;padding:6px;box-shadow:0 8px 28px #0008}}
.menu button{{display:block;width:100%;text-align:left;border:0;background:transparent}}
.notice{{margin:20px 0;padding:12px 16px;border-left:3px solid #d6aa75;background:#22272d}}
.panel{{margin-top:28px;padding:20px;border:1px solid #363c43;border-radius:12px}}
.muted{{color:#bec4ca}}.status{{min-height:24px}}iframe{{width:100%;height:620px;border:1px solid #464e57;border-radius:8px;background:#171b20}}
[hidden]{{display:none!important}}
</style></head><body><main>
<div class="bar"><span class="brand">SIGMA</span><span class="muted">Administrator preview</span>
<div><button id="chatgpt-pill" class="pill" aria-haspopup="menu" aria-expanded="false">ChatGPT</button>
<div id="mode-menu" class="menu" role="menu" hidden><button id="personal-mode" role="menuitem">Personal</button></div></div></div>
<p class="notice"><strong>Synthetic preview only.</strong> Do not sign in to OpenAI or enter credentials. This isolated browser displays the disabled laboratory page.</p>
<section id="personal-panel" class="panel" hidden aria-label="Personal ChatGPT preview">
<h1>Personal · synthetic preview</h1><p class="muted">This checks the private browser handshake only. Account discovery and inference remain disabled.</p>
<button id="open-browser">Open synthetic browser</button>
<button id="close-browser" hidden>Close browser</button>
<p id="status" class="status" role="status" aria-live="polite">Browser stopped.</p>
<iframe id="browser" title="Synthetic browser preview" hidden></iframe>
</section></main>
<script nonce="{nonce}">
const prefix={json.dumps(PREFIX)};
const pill=document.querySelector('#chatgpt-pill'), menu=document.querySelector('#mode-menu');
const panel=document.querySelector('#personal-panel'), status=document.querySelector('#status');
const frame=document.querySelector('#browser'), open=document.querySelector('#open-browser'), close=document.querySelector('#close-browser');
pill.addEventListener('click',()=>{{menu.hidden=!menu.hidden;pill.setAttribute('aria-expanded',String(!menu.hidden));}});
document.querySelector('#personal-mode').addEventListener('click',()=>{{menu.hidden=true;pill.setAttribute('aria-expanded','false');panel.hidden=false;}});
async function action(name){{const response=await fetch(prefix+'/api/'+name,{{method:'POST',cache:'no-store',credentials:'same-origin'}});if(!response.ok)throw new Error('Synthetic browser is unavailable.');return response.json();}}
open.addEventListener('click',async()=>{{open.disabled=true;status.textContent='Starting the isolated synthetic browser…';try{{await action('start');frame.src=prefix+'/window';frame.hidden=false;close.hidden=false;status.textContent='Synthetic browser ready. OpenAI sign-in is disabled.';}}catch(e){{status.textContent=e.message;}}finally{{open.disabled=false;}}}});
close.addEventListener('click',async()=>{{close.disabled=true;frame.src='about:blank';frame.hidden=true;status.textContent='Stopping synthetic browser…';try{{await action('stop');status.textContent='Browser stopped. State is retained for reopen testing.';}}catch(e){{status.textContent=e.message;}}finally{{close.disabled=false;close.hidden=true;}}}});
</script></body></html>"""
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'none'; "
                f"script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                "connect-src 'self'; frame-src 'self'; form-action 'none'; "
                "base-uri 'none'; frame-ancestors 'none'"
            ),
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.post(PREFIX + "/api/start", include_in_schema=False)
async def start(request: Request) -> dict[str, str | bool | None]:
    _require_preview_path(request)
    _origin_allowed(request)
    if request.headers.get("content-length", "0") not in {"", "0"}:
        raise HTTPException(400, "Invalid preview request.")
    try:
        return await personal_browser.session(request.state.cloud_principal, "start")
    except personal_browser.PersonalBrowserUnavailable as exc:
        raise HTTPException(503, "Synthetic browser is unavailable.") from exc


@app.get(PREFIX + "/api/status", include_in_schema=False)
async def status(request: Request) -> dict[str, str | bool | None]:
    _require_preview_path(request)
    try:
        return await personal_browser.session(request.state.cloud_principal, "status")
    except personal_browser.PersonalBrowserUnavailable as exc:
        raise HTTPException(503, "Synthetic browser is unavailable.") from exc


@app.post(PREFIX + "/api/stop", include_in_schema=False)
async def stop(request: Request) -> dict[str, str | bool | None]:
    _require_preview_path(request)
    _origin_allowed(request)
    if request.headers.get("content-length", "0") not in {"", "0"}:
        raise HTTPException(400, "Invalid preview request.")
    try:
        return await personal_browser.session(request.state.cloud_principal, "stop")
    except personal_browser.PersonalBrowserUnavailable as exc:
        raise HTTPException(503, "Synthetic browser is unavailable.") from exc


@app.get(PREFIX + "/assets/{path:path}", include_in_schema=False)
async def asset(request: Request, path: str) -> Response:
    _require_preview_path(request)
    try:
        return await personal_browser_proxy.asset(request, path)
    except HTTPException as exc:
        return Response(
            str(exc.detail).encode("utf-8"),
            status_code=exc.status_code,
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )


@app.get(PREFIX + "/window", response_class=HTMLResponse, include_in_schema=False)
async def window(request: Request) -> HTMLResponse:
    _require_preview_path(request)
    principal = request.state.cloud_principal
    try:
        await personal_browser_proxy._ready(principal)
        password = await personal_browser.browser_password(principal)
    except personal_browser.PersonalBrowserUnavailable as exc:
        raise HTTPException(503, "Synthetic browser is unavailable.") from exc
    nonce = secrets.token_urlsafe(20)
    script = f"""
import RFB from {json.dumps(PREFIX + "/assets/app/rfb.js")};
const target=document.querySelector('#screen');
const status=document.querySelector('#connection-status');
const scheme=location.protocol==='https:'?'wss:':'ws:';
const rfb=new RFB(target,scheme+'//'+location.host+{json.dumps(PREFIX + "/ws")},{{credentials:{{password:{json.dumps(password)}}}}});
rfb.scaleViewport=true;rfb.resizeSession=true;
rfb.addEventListener('connect',()=>{{status.textContent='Synthetic browser connected';}});
rfb.addEventListener('disconnect',()=>{{status.textContent='Preview stream ended. Close and reopen from SIGMA to reauthorize.';}});
"""
    html = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'><link rel='icon' href='data:,'>"
        "<title>SIGMA · Synthetic browser</title>"
        f"<style nonce='{nonce}'>html,body{{margin:0;background:#171b20;color:#fff;font:14px system-ui;height:100%}}"
        "main{display:flex;flex-direction:column;height:100%;overflow:hidden}"
        "header{padding:8px 16px;background:#20252b;display:flex;gap:16px}"
        "#screen{flex:1;min-height:0;overflow:hidden}#screen canvas{outline:none}"
        "</style></head><body><main><header><strong>Synthetic preview — do not sign in to OpenAI</strong>"
        "<span id='connection-status'>Opening private browser…</span></header>"
        "<div id='screen'></div></main>"
        f"<script type='module' nonce='{nonce}'>{script}</script></body></html>"
    )
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": (
                "default-src 'none'; "
                f"script-src 'self' 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                "connect-src 'self' ws: wss:; img-src 'self' data:; "
                "font-src 'self'; frame-ancestors 'self'"
            ),
        },
    )


@app.websocket(PREFIX + "/ws")
async def websocket(websocket: WebSocket) -> None:
    """Edge auth checks the admin on upgrade; cap each stream at one minute."""
    if websocket.headers.get("origin") != _ORIGIN:
        await websocket.close(code=1008)
        return
    principal = websocket.scope.get("state", {}).get("cloud_principal")
    if not isinstance(principal, cloud_auth.Principal) or principal.role != "admin":
        await websocket.close(code=1008)
        return
    try:
        if (await personal_browser.session(principal))["browser_status"] != "ready":
            await websocket.close(code=1013)
            return
        socket_path = await personal_browser.browser_socket(principal)
        reader, writer = await personal_browser_proxy._connect_worker(socket_path)
    except (OSError, ValueError, personal_browser.PersonalBrowserUnavailable):
        await websocket.close(code=1013)
        return
    selected_protocol = (
        "binary"
        if "binary" in (websocket.headers.get("sec-websocket-protocol") or "").split(",")
        else None
    )
    await websocket.accept(subprotocol=selected_protocol)

    async def from_browser() -> None:
        while True:
            item = await websocket.receive()
            if item["type"] == "websocket.disconnect":
                return
            if item["type"] != "websocket.receive":
                continue
            if item.get("bytes") is not None:
                writer.write(personal_browser_proxy._masked_frame(2, item["bytes"]))
            else:
                writer.write(
                    personal_browser_proxy._masked_frame(1, (item.get("text") or "").encode())
                )
            await writer.drain()

    async def from_worker() -> None:
        fragments = bytearray()
        fragment_opcode: int | None = None
        while True:
            fin, opcode, payload = await personal_browser_proxy._remote_frame(reader)
            if opcode == 8:
                return
            if opcode == 9:
                writer.write(personal_browser_proxy._masked_frame(10, payload))
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
                raise ValueError("Oversized RFB message")
            if fin:
                if fragment_opcode == 2:
                    await websocket.send_bytes(bytes(fragments))
                else:
                    await websocket.send_text(fragments.decode("utf-8"))
                fragments.clear()
                fragment_opcode = None

    async def expire() -> None:
        await asyncio.sleep(_MAX_WS_SECONDS)

    tasks = [
        asyncio.create_task(from_browser()),
        asyncio.create_task(from_worker()),
        asyncio.create_task(expire()),
    ]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for task in done:
            if not task.cancelled():
                task.result()
    except (OSError, ValueError, UnicodeError, asyncio.IncompleteReadError, TimeoutError):
        pass
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass
        try:
            await websocket.close()
        except (RuntimeError, OSError):
            pass
